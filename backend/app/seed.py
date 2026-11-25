"""Local test data seeder for EAMT 2028 (never run in production)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import get_upload_dir
from app.core.database import engine, init_db, is_sqlite_engine
from app.core.security import hash_password
from app.models.models import (
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


def _escape_pdf_text(text: str) -> str:
    ascii_safe = text.encode("latin-1", "replace").decode("latin-1")
    return ascii_safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_real_pdf(title: str, abstract: str) -> bytes:
    """Create a minimal valid single-page anonymized PDF document."""
    safe_title = _escape_pdf_text(title[:90])
    safe_abstract = _escape_pdf_text(abstract[:180])
    content_stream = (
        f"BT /F1 14 Tf 50 740 Td ({safe_title}) Tj "
        f"0 -28 Td /F1 10 Tf (Anonymous Manuscript - Double-Blind Copy) Tj "
        f"0 -24 Td ({safe_abstract}) Tj ET"
    ).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1")
            + content_stream
            + b"\nendstream\nendobj\n"
        ),
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(buf))
        buf.extend(obj)

    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    buf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    buf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(buf)


def seed_database() -> None:
    if is_sqlite_engine():
        init_db()

    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            print("Database already seeded; skipping.")
            return

        now = datetime.now(timezone.utc)
        password_hashed = hash_password("password")

        user_specs = [
            (
                "chair",
                User(
                    email="chair@example.com",
                    password_hash=password_hashed,
                    first_name="Chair",
                    last_name="User",
                    affiliation="EAMT 2028 Programme Chair · Utrecht University",
                    expertise="Conference organization, machine translation, evaluation",
                ),
                [Role.organizer],
            ),
            (
                "organizer",
                User(
                    email="organizer@example.com",
                    password_hash=password_hashed,
                    first_name="Diana",
                    last_name="Vandenberg",
                    affiliation="EAMT 2028 Programme Chair · Utrecht University",
                    expertise="Conference organization, machine translation, evaluation",
                ),
                [Role.organizer],
            ),
            (
                "author",
                User(
                    email="author@example.com",
                    password_hash=password_hashed,
                    first_name="Alice",
                    last_name="Smith",
                    affiliation="University of Amsterdam",
                    expertise="Neural machine translation, low-resource NLP, privacy-preserving AI",
                ),
                [Role.author],
            ),
            (
                "reviewer",
                User(
                    email="reviewer@example.com",
                    password_hash=password_hashed,
                    first_name="Charlie",
                    last_name="Brown",
                    affiliation="TU Delft",
                    expertise="Neural machine translation, transformer attention, multilingual NLP, privacy",
                ),
                [Role.reviewer],
            ),
            (
                "reviewer2",
                User(
                    email="reviewer2@example.com",
                    password_hash=password_hashed,
                    first_name="Maya",
                    last_name="Bennett",
                    affiliation="University of Edinburgh",
                    expertise="Statistical & neural machine translation, COMET evaluation, corpus alignment",
                ),
                [Role.reviewer],
            ),
            (
                "reviewer3",
                User(
                    email="reviewer3@example.com",
                    password_hash=password_hashed,
                    first_name="Noah",
                    last_name="Williams",
                    affiliation="ETH Zurich",
                    expertise="Software security, differential privacy, federated transformer training",
                ),
                [Role.reviewer],
            ),
            (
                "admin",
                User(
                    email="admin@example.com",
                    password_hash=password_hashed,
                    first_name="Admin",
                    last_name="Supervisor",
                    affiliation="EAMT Infrastructure Ops",
                    expertise="Infrastructure security, compliance",
                ),
                [Role.admin],
            ),
            (
                "guest",
                User(
                    email="guest@example.com",
                    password_hash=password_hashed,
                    first_name="Guest",
                    last_name="Observer",
                    affiliation="EAMT Advisory Board",
                    expertise="Machine translation policy",
                ),
                [Role.author, Role.guest],
            ),
            (
                "demo",
                User(
                    email="demo@eamt.org",
                    password_hash=password_hashed,
                    first_name="Demo",
                    last_name="User",
                    affiliation="EAMT 2028 Demo Lab",
                    expertise="Neural machine translation, evaluation, software security",
                ),
                [Role.author, Role.reviewer, Role.organizer, Role.admin],
            ),
        ]

        users_by_key: dict[str, User] = {}
        for key, user, roles in user_specs:
            session.add(user)
            session.flush()
            for role in roles:
                session.add(UserRole(user_id=user.id, role=role))
            users_by_key[key] = user

        eamt_2028 = Conference(
            name="EAMT 2028",
            description="29th Annual Conference of the European Association for Machine Translation — Secure AI Track",
            submission_deadline=now + timedelta(days=30),
            review_deadline=now + timedelta(days=60),
            notification_deadline=now + timedelta(days=90),
        )
        eamt_2027 = Conference(
            name="EAMT 2027 (Released)",
            description="28th Annual Conference — Final Decisions & Anonymized Reviews Released",
            submission_deadline=now - timedelta(days=90),
            review_deadline=now - timedelta(days=45),
            notification_deadline=now - timedelta(days=15),
        )
        session.add_all([eamt_2028, eamt_2027])
        session.flush()

        upload_dir = get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        def _create_submission(
            conf: Conference,
            author: User,
            title: str,
            abstract: str,
            status: SubmissionStatus,
        ) -> Submission:
            sub_id = uuid.uuid4()
            pdf_path = upload_dir / f"{sub_id}.pdf"
            pdf_path.write_bytes(_build_real_pdf(title, abstract))
            sub = Submission(
                id=sub_id,
                conference_id=conf.id,
                author_id=author.id,
                title=title,
                abstract=abstract,
                file_path=str(pdf_path),
                status=status,
            )
            session.add(sub)
            return sub

        paper_1 = _create_submission(
            eamt_2028,
            users_by_key["guest"],
            "Zero-Shot Terminology Injection in Domain-Adapted Transformer Decoders",
            "We evaluate constrained beam search and lightweight adapter modules for domain-specific terminology adherence in enterprise translation pipelines.",
            SubmissionStatus.accepted,
        )
        paper_2 = _create_submission(
            eamt_2028,
            users_by_key["author"],
            "Calibrated Quality Estimation for Low-Resource European Machine Translation",
            "An empirical study on reference-free COMET metrics and cross-lingual corpus alignment across twelve low-resource European language pairs.",
            SubmissionStatus.submitted,
        )
        paper_3 = _create_submission(
            eamt_2028,
            users_by_key["author"],
            "Privacy-Preserving Neural Machine Translation with Differential Attention",
            "We propose a transformer-based neural machine translation architecture enforcing differential privacy and double-blind confidentiality guarantees for low-resource multilingual corpora.",
            SubmissionStatus.submitted,
        )
        paper_released = _create_submission(
            eamt_2027,
            users_by_key["demo"],
            "Auditable Double-Blind Workflows for Machine Translation Peer Review",
            "A practical security architecture for stripping author metadata and preventing conflict-of-interest assignments in academic conferences.",
            SubmissionStatus.accepted,
        )
        session.flush()

        session.add(
            CoAuthor(
                submission_id=paper_3.id,
                name="Bob Jones",
                email="bob.jones@uva.nl",
                affiliation="University of Amsterdam",
            )
        )

        session.add_all(
            [
                Review(
                    submission_id=paper_1.id,
                    reviewer_id=users_by_key["reviewer2"].id,
                    status=InvitationStatus.accepted,
                    score=5,
                    confidence=4,
                    comments="Excellent adapter design with clear ablation tables and strong terminology precision.",
                ),
                Review(
                    submission_id=paper_2.id,
                    reviewer_id=users_by_key["demo"].id,
                    status=InvitationStatus.accepted,
                ),
                Review(
                    submission_id=paper_3.id,
                    reviewer_id=users_by_key["reviewer3"].id,
                    status=InvitationStatus.invited,
                ),
                Review(
                    submission_id=paper_3.id,
                    reviewer_id=users_by_key["reviewer"].id,
                    status=InvitationStatus.accepted,
                    score=4,
                    confidence=5,
                    comments="Strong privacy guarantees and thorough evaluation against baseline transformers.",
                ),
                Review(
                    submission_id=paper_released.id,
                    reviewer_id=users_by_key["reviewer"].id,
                    status=InvitationStatus.accepted,
                    score=5,
                    confidence=5,
                    comments="Well-engineered double-blind pipeline with crisp empirical security validation.",
                ),
            ]
        )

        demo_invite_token = "eamt-2028-demo-reviewer-invite"
        session.add_all(
            [
                Invitation(
                    conference_id=eamt_2028.id,
                    email="invited.reviewer@example.com",
                    role=Role.reviewer,
                    status=InvitationStatus.invited,
                    token_hash=hashlib.sha256(demo_invite_token.encode("utf-8")).hexdigest(),
                    expires_at=now + timedelta(days=14),
                ),
                Invitation(
                    conference_id=eamt_2028.id,
                    email="reviewer@example.com",
                    role=Role.reviewer,
                    status=InvitationStatus.accepted,
                    token_hash=hashlib.sha256(b"accepted-demo-token").hexdigest(),
                    expires_at=now + timedelta(days=14),
                ),
            ]
        )

        session.commit()
        print("Seeded EAMT 2028 demo database.")
        print(
            "Accounts (password: 'password'): "
            "chair@example.com, organizer@example.com, author@example.com, "
            "reviewer@example.com, reviewer2@example.com, reviewer3@example.com, "
            "admin@example.com, guest@example.com, demo@eamt.org"
        )
        print(f"Open demo reviewer invitation token: {demo_invite_token}")


if __name__ == "__main__":
    seed_database()
