"""
Shared pytest fixtures for CMT integration tests.

Schema mirrors docs/database.dbml (users, user_roles, conferences, invitations,
submissions, co_authors, reviews). By default, tests run against an isolated
in-memory SQLite database so TDD runs work offline without external setup.
Set TEST_DATABASE_URL (e.g. mysql+pymysql://...) to execute directly against MySQL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    insert,
)
from sqlalchemy.pool import StaticPool

# Ensure app.core.database can be imported even when no local .env file exists.
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_DATABASE", "cmt_test")
os.environ.setdefault("MYSQL_USER", "cmt_user")
os.environ.setdefault("MYSQL_PASSWORD", "test_password")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

TEST_JWT_SECRET = os.getenv("SECRET_KEY", "test-secret-key-for-integration-tests")


# ---------------------------------------------------------------------------
# Database schema matching docs/database.dbml
# ---------------------------------------------------------------------------
test_metadata = MetaData()

users_table = Table(
    "users",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("first_name", String(100), nullable=False),
    Column("last_name", String(100), nullable=False),
    Column("affiliation", String(255), nullable=True),
    Column("expertise", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

user_roles_table = Table(
    "user_roles",
    test_metadata,
    Column("user_id", String(36), ForeignKey("users.id"), primary_key=True),
    Column("role", String(32), primary_key=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

conferences_table = Table(
    "conferences",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
    Column("submission_deadline", DateTime, nullable=False),
    Column("review_deadline", DateTime, nullable=False),
    Column("notification_deadline", DateTime, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

invitations_table = Table(
    "invitations",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("conference_id", String(36), ForeignKey("conferences.id"), nullable=False),
    Column("email", String(255), nullable=False),
    Column("role", String(32), nullable=False),
    Column("status", String(32), nullable=False, default="invited"),
    Column("token_hash", String(255), nullable=False, unique=True),
    Column("expires_at", DateTime, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

submissions_table = Table(
    "submissions",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("conference_id", String(36), ForeignKey("conferences.id"), nullable=False),
    Column("author_id", String(36), ForeignKey("users.id"), nullable=False),
    Column("title", String(500), nullable=False),
    Column("abstract", Text, nullable=False),
    Column("file_path", String(500), nullable=False),
    Column("status", String(32), nullable=False, default="submitted"),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

co_authors_table = Table(
    "co_authors",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("submission_id", String(36), ForeignKey("submissions.id"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("email", String(255), nullable=False),
    Column("affiliation", String(255), nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

reviews_table = Table(
    "reviews",
    test_metadata,
    Column("id", String(36), primary_key=True),
    Column("submission_id", String(36), ForeignKey("submissions.id"), nullable=False),
    Column("reviewer_id", String(36), ForeignKey("users.id"), nullable=False),
    Column("status", String(32), nullable=False, default="invited"),
    Column("score", Integer, nullable=True),
    Column("confidence", Integer, nullable=True),
    Column("comments", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("submission_id", "reviewer_id", name="uq_submission_reviewer"),
)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_test_jwt(user_id: str, email: str, roles: list[str], expired: bool = False) -> str:
    """Create a signed HS256 JWT (delegates to app.core.security once implemented)."""
    if not expired:
        try:
            from app.core.security import create_access_token  # type: ignore

            return create_access_token({"sub": user_id, "email": email, "roles": roles})
        except (ImportError, AttributeError):
            pass

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    exp_delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "exp": int((datetime.now(timezone.utc) + exp_delta).timestamp()),
    }
    signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    signature = hmac.new(
        TEST_JWT_SECRET.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url(signature)}"


# ---------------------------------------------------------------------------
# Core Infrastructure Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def test_engine():
    db_url = os.getenv("TEST_DATABASE_URL")
    if db_url:
        engine = create_engine(db_url)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    test_metadata.create_all(engine)
    yield engine
    test_metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_conn(test_engine):
    """Wrap each test in a rolled-back transaction so database state stays isolated."""
    connection = test_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(directory))
    return directory


@pytest.fixture
def client(db_conn, upload_dir):
    """FastAPI TestClient wired to the test database dependency (when defined)."""
    import app.core.database as db_module

    get_db = getattr(db_module, "get_db", None)
    if get_db is not None:
        def _override_get_db():
            yield db_conn

        app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """Minimal syntactically valid PDF containing %PDF- magic bytes and author metadata."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
        b"3 0 obj << /Author (Alice Smith) /Creator (University of Amsterdam) >> endobj\n"
        b"trailer << /Root 1 0 R /Info 3 0 R >>\n"
        b"%%EOF\n"
    )


# ---------------------------------------------------------------------------
# Seeded Domain Fixtures (matching docs/database.dbml)
# ---------------------------------------------------------------------------
@pytest.fixture
def seeded_users(db_conn) -> dict[str, dict]:
    now = _utcnow_naive()
    users = {
        "alice": {
            "id": str(uuid.uuid4()),
            "email": "alice.smith@uva.nl",
            "password_hash": "$2b$12$placeholderhashforalice000000000000000000000000000000",
            "first_name": "Alice",
            "last_name": "Smith",
            "affiliation": "University of Amsterdam",
            "expertise": "Neural machine translation, low-resource NLP",
            "roles": ["author", "reviewer"],
        },
        "bob": {
            "id": str(uuid.uuid4()),
            "email": "bob.jones@uva.nl",
            "password_hash": "$2b$12$placeholderhashforbob00000000000000000000000000000000",
            "first_name": "Bob",
            "last_name": "Jones",
            "affiliation": "University of Amsterdam",
            "expertise": "Machine translation evaluation, transformer architectures",
            "roles": ["author", "reviewer"],
        },
        "charlie": {
            "id": str(uuid.uuid4()),
            "email": "charlie.brown@tudelft.nl",
            "password_hash": "$2b$12$placeholderhashforcharlie0000000000000000000000000000",
            "first_name": "Charlie",
            "last_name": "Brown",
            "affiliation": "TU Delft",
            "expertise": "Neural machine translation, transformer attention, multilingual NLP",
            "roles": ["author", "reviewer"],
        },
        "dave": {
            "id": str(uuid.uuid4()),
            "email": "dave.miller@vu.nl",
            "password_hash": "$2b$12$placeholderhashfordave0000000000000000000000000000000",
            "first_name": "Dave",
            "last_name": "Miller",
            "affiliation": "VU Amsterdam",
            "expertise": "Computer vision, 3D image segmentation",
            "roles": ["author", "reviewer"],
        },
        "diana": {
            "id": str(uuid.uuid4()),
            "email": "diana.chair@eamt.org",
            "password_hash": "$2b$12$placeholderhashfordiana000000000000000000000000000000",
            "first_name": "Diana",
            "last_name": "Chair",
            "affiliation": "EAMT 2028 Committee",
            "expertise": "Conference organization, machine translation",
            "roles": ["author", "organizer"],
        },
    }

    for user in users.values():
        db_conn.execute(
            insert(users_table).values(
                id=user["id"],
                email=user["email"],
                password_hash=user["password_hash"],
                first_name=user["first_name"],
                last_name=user["last_name"],
                affiliation=user["affiliation"],
                expertise=user["expertise"],
                created_at=now,
                updated_at=now,
            )
        )
        for role in user["roles"]:
            db_conn.execute(
                insert(user_roles_table).values(
                    user_id=user["id"],
                    role=role,
                    created_at=now,
                    updated_at=now,
                )
            )
    return users


@pytest.fixture
def auth_headers(seeded_users):
    """Build Authorization Bearer headers for any seeded user."""
    def _for_user(key: str, expired: bool = False) -> dict[str, str]:
        u = seeded_users[key]
        token = _build_test_jwt(u["id"], u["email"], u["roles"], expired=expired)
        return {"Authorization": f"Bearer {token}"}

    return _for_user


@pytest.fixture
def active_conference(db_conn) -> dict:
    now = _utcnow_naive()
    conf = {
        "id": str(uuid.uuid4()),
        "name": "EAMT 2028",
        "description": "European Association for Machine Translation Conference 2028",
        "submission_deadline": now + timedelta(days=7),
        "review_deadline": now + timedelta(days=21),
        "notification_deadline": now + timedelta(days=30),
    }
    db_conn.execute(
        insert(conferences_table).values(**conf, created_at=now, updated_at=now)
    )
    return conf


@pytest.fixture
def expired_conference(db_conn) -> dict:
    now = _utcnow_naive()
    conf = {
        "id": str(uuid.uuid4()),
        "name": "EAMT 2027 (Closed)",
        "description": "Past conference whose submission deadline has already elapsed",
        "submission_deadline": now - timedelta(days=2),
        "review_deadline": now + timedelta(days=5),
        "notification_deadline": now + timedelta(days=10),
    }
    db_conn.execute(
        insert(conferences_table).values(**conf, created_at=now, updated_at=now)
    )
    return conf


@pytest.fixture
def seeded_submission(db_conn, seeded_users, active_conference, upload_dir, valid_pdf_bytes) -> dict:
    """Seed a paper authored by Alice with Bob listed in co_authors."""
    now = _utcnow_naive()
    sub_id = str(uuid.uuid4())
    pdf_path = upload_dir / f"{sub_id}.pdf"
    pdf_path.write_bytes(valid_pdf_bytes)

    db_conn.execute(
        insert(submissions_table).values(
            id=sub_id,
            conference_id=active_conference["id"],
            author_id=seeded_users["alice"]["id"],
            title="Privacy-Preserving Neural Machine Translation",
            abstract="We introduce a transformer-based neural machine translation pipeline with strict confidentiality guarantees.",
            file_path=str(pdf_path),
            status="submitted",
            created_at=now,
            updated_at=now,
        )
    )
    db_conn.execute(
        insert(co_authors_table).values(
            id=str(uuid.uuid4()),
            submission_id=sub_id,
            name="Bob Jones",
            email=seeded_users["bob"]["email"],
            affiliation=seeded_users["bob"]["affiliation"],
            created_at=now,
            updated_at=now,
        )
    )
    return {
        "id": sub_id,
        "conference_id": active_conference["id"],
        "author_id": seeded_users["alice"]["id"],
        "author_email": seeded_users["alice"]["email"],
        "author_name": "Alice Smith",
        "co_author_id": seeded_users["bob"]["id"],
        "file_path": str(pdf_path),
    }


@pytest.fixture
def seeded_assigned_submission(db_conn, seeded_users, seeded_submission) -> dict:
    """Assign Charlie (accepted review) to Alice's submission; Dave remains unassigned."""
    now = _utcnow_naive()
    review_id = str(uuid.uuid4())
    db_conn.execute(
        insert(reviews_table).values(
            id=review_id,
            submission_id=seeded_submission["id"],
            reviewer_id=seeded_users["charlie"]["id"],
            status="accepted",
            score=4,
            confidence=5,
            comments="Strong experimental evaluation and clear security framing.",
            created_at=now,
            updated_at=now,
        )
    )
    return {
        **seeded_submission,
        "review_id": review_id,
        "assigned_reviewer_key": "charlie",
        "unassigned_reviewer_key": "dave",
    }


@pytest.fixture
def seeded_expired_invitation(db_conn, active_conference) -> dict:
    """Seed an expired reviewer invitation whose token is stored as a SHA-256 hash."""
    now = _utcnow_naive()
    inv_id = str(uuid.uuid4())
    raw_token = "expired-secret-invite-token-eamt-2028"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    db_conn.execute(
        insert(invitations_table).values(
            id=inv_id,
            conference_id=active_conference["id"],
            email="new.reviewer@uni.nl",
            role="reviewer",
            status="invited",
            token_hash=token_hash,
            expires_at=now - timedelta(hours=1),
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        )
    )
    return {
        "id": inv_id,
        "raw_token": raw_token,
        "token_hash": token_hash,
        "email": "new.reviewer@uni.nl",
    }
