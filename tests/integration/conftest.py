"""
Pytest fixtures for CMT component/integration tests.

Uses the real SQLModel models from app.models.models and overrides
app.core.database.get_session so tests run against an isolated in-memory SQLite
database by default (or MySQL when TEST_DATABASE_URL is configured).
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
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Ensure app.core.database can be imported even when no local .env file exists.
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_DATABASE", "cmt_test")
os.environ.setdefault("MYSQL_USER", "cmt_user")
os.environ.setdefault("MYSQL_PASSWORD", "test_password")

from fastapi.testclient import TestClient  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    CoAuthor,
    Conference,
    Invitation,
    InvitationStatus,
    Review,
    Role,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)

TEST_JWT_SECRET = os.getenv("SECRET_KEY", "test-secret-key-for-integration-tests")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_test_jwt(
    user_id: uuid.UUID, email: str, roles: list[Role], expired: bool = False
) -> str:
    """Create a signed HS256 JWT (delegates to app.core.security once implemented)."""
    role_values = [r.value for r in roles]
    if not expired:
        try:
            from app.core.security import create_access_token  # type: ignore

            return create_access_token(
                {"sub": str(user_id), "email": email, "roles": role_values}
            )
        except (ImportError, AttributeError):
            pass

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    exp_delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": role_values,
        "exp": int((datetime.now(timezone.utc) + exp_delta).timestamp()),
    }
    signing_input = (
        f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    )
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
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Wrap each test in a rolled-back transaction so database state stays isolated."""
    connection = test_engine.connect()
    transaction = connection.begin()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        yield session
    transaction.rollback()
    connection.close()


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(directory))
    return directory


@pytest.fixture
def client(db_session, upload_dir):
    """FastAPI TestClient wired to the isolated test SQLModel session."""
    def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seeded Domain Fixtures (matching app.models.models / docs/database.dbml)
# ---------------------------------------------------------------------------
@pytest.fixture
def seeded_users(db_session: Session) -> dict[str, dict]:
    specs = {
        "alice": (
            User(
                email="alice.smith@uva.nl",
                password_hash="$2b$12$placeholderhashforalice000000000000000000000000000000",
                first_name="Alice",
                last_name="Smith",
                affiliation="University of Amsterdam",
                expertise="Neural machine translation, low-resource NLP",
            ),
            [Role.author, Role.reviewer],
        ),
        "bob": (
            User(
                email="bob.jones@uva.nl",
                password_hash="$2b$12$placeholderhashforbob00000000000000000000000000000000",
                first_name="Bob",
                last_name="Jones",
                affiliation="University of Amsterdam",
                expertise="Machine translation evaluation, transformer architectures",
            ),
            [Role.author, Role.reviewer],
        ),
        "charlie": (
            User(
                email="charlie.brown@tudelft.nl",
                password_hash="$2b$12$placeholderhashforcharlie0000000000000000000000000000",
                first_name="Charlie",
                last_name="Brown",
                affiliation="TU Delft",
                expertise="Neural machine translation, transformer attention, multilingual NLP",
            ),
            [Role.author, Role.reviewer],
        ),
        "dave": (
            User(
                email="dave.miller@vu.nl",
                password_hash="$2b$12$placeholderhashfordave0000000000000000000000000000000",
                first_name="Dave",
                last_name="Miller",
                affiliation="VU Amsterdam",
                expertise="Computer vision, 3D image segmentation",
            ),
            [Role.author, Role.reviewer],
        ),
        "diana": (
            User(
                email="diana.chair@eamt.org",
                password_hash="$2b$12$placeholderhashfordiana000000000000000000000000000000",
                first_name="Diana",
                last_name="Chair",
                affiliation="EAMT 2028 Committee",
                expertise="Conference organization, machine translation",
            ),
            [Role.author, Role.organizer],
        ),
    }

    seeded: dict[str, dict] = {}
    for key, (user, roles) in specs.items():
        db_session.add(user)
        db_session.flush()
        for role in roles:
            db_session.add(UserRole(user_id=user.id, role=role))
        seeded[key] = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "affiliation": user.affiliation,
            "expertise": user.expertise,
            "roles": roles,
        }
    db_session.flush()
    return seeded


@pytest.fixture
def auth_headers(seeded_users):
    """Build Authorization Bearer headers for any seeded user."""
    def _for_user(key: str, expired: bool = False) -> dict[str, str]:
        u = seeded_users[key]
        token = _build_test_jwt(u["id"], u["email"], u["roles"], expired=expired)
        return {"Authorization": f"Bearer {token}"}

    return _for_user


@pytest.fixture
def active_conference(db_session: Session) -> Conference:
    now = _utcnow()
    conf = Conference(
        name="EAMT 2028",
        description="European Association for Machine Translation Conference 2028",
        submission_deadline=now + timedelta(days=7),
        review_deadline=now + timedelta(days=21),
        notification_deadline=now + timedelta(days=30),
    )
    db_session.add(conf)
    db_session.flush()
    return conf


@pytest.fixture
def expired_conference(db_session: Session) -> Conference:
    now = _utcnow()
    conf = Conference(
        name="EAMT 2027 (Closed)",
        description="Past conference whose submission deadline has already elapsed",
        submission_deadline=now - timedelta(days=2),
        review_deadline=now + timedelta(days=5),
        notification_deadline=now + timedelta(days=10),
    )
    db_session.add(conf)
    db_session.flush()
    return conf


@pytest.fixture
def seeded_submission(
    db_session: Session,
    seeded_users: dict[str, dict],
    active_conference: Conference,
    upload_dir: Path,
    valid_pdf_bytes: bytes,
) -> dict:
    """Seed a paper authored by Alice with Bob listed in co_authors."""
    sub_id = uuid.uuid4()
    pdf_path = upload_dir / f"{sub_id}.pdf"
    pdf_path.write_bytes(valid_pdf_bytes)

    sub = Submission(
        id=sub_id,
        conference_id=active_conference.id,
        author_id=seeded_users["alice"]["id"],
        title="Privacy-Preserving Neural Machine Translation",
        abstract=(
            "We introduce a transformer-based neural machine translation pipeline "
            "with strict confidentiality guarantees."
        ),
        file_path=str(pdf_path),
        status=SubmissionStatus.submitted,
    )
    db_session.add(sub)
    db_session.flush()

    db_session.add(
        CoAuthor(
            submission_id=sub.id,
            name="Bob Jones",
            email=seeded_users["bob"]["email"],
            affiliation=seeded_users["bob"]["affiliation"],
        )
    )
    db_session.flush()

    return {
        "id": sub.id,
        "conference_id": active_conference.id,
        "author_id": seeded_users["alice"]["id"],
        "author_email": seeded_users["alice"]["email"],
        "author_name": "Alice Smith",
        "co_author_id": seeded_users["bob"]["id"],
        "file_path": str(pdf_path),
    }


@pytest.fixture
def seeded_assigned_submission(
    db_session: Session,
    seeded_users: dict[str, dict],
    seeded_submission: dict,
) -> dict:
    """Assign Charlie (accepted review) to Alice's submission; Dave remains unassigned."""
    review = Review(
        submission_id=seeded_submission["id"],
        reviewer_id=seeded_users["charlie"]["id"],
        status=InvitationStatus.accepted,
        score=4,
        confidence=5,
        comments="Strong experimental evaluation and clear security framing.",
    )
    db_session.add(review)
    db_session.flush()
    return {
        **seeded_submission,
        "review_id": review.id,
        "assigned_reviewer_key": "charlie",
        "unassigned_reviewer_key": "dave",
    }


@pytest.fixture
def seeded_expired_invitation(
    db_session: Session, active_conference: Conference
) -> dict:
    """Seed an expired reviewer invitation whose token is stored as a SHA-256 hash."""
    now = _utcnow()
    raw_token = "expired-secret-invite-token-eamt-2028"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    inv = Invitation(
        conference_id=active_conference.id,
        email="new.reviewer@uni.nl",
        role=Role.reviewer,
        status=InvitationStatus.invited,
        token_hash=token_hash,
        expires_at=now - timedelta(hours=1),
    )
    db_session.add(inv)
    db_session.flush()
    return {
        "id": inv.id,
        "raw_token": raw_token,
        "token_hash": token_hash,
        "email": inv.email,
    }
