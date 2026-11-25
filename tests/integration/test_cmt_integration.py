"""
Task 5 - QA: Component / Integration Tests (5 total: 2 Functional, 3 Security = 60% Security).

Each test exercises multiple collaborating components from the C4 architecture
(FastAPI API modules <-> Auth/RBAC <-> File Storage / AI Provider <-> Database)
and traces directly to the SRS requirements (US, FR, NFR, SEC) and app.models.models.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.models.models import (
    CoAuthor,
    Invitation,
    InvitationStatus,
    Review,
    Submission,
    SubmissionStatus,
)


# =============================================================================
# IT-01 (Functional): End-to-End Paper Submission, Co-Authors & Deadline Check
# SRS Traceability: US-03, US-05, FR-02, NFR-03
# Components: FastAPI (Submissions) <-> Auth <-> File Storage <-> Database
# =============================================================================
@pytest.mark.integration
@pytest.mark.functional
def test_it01_paper_submission_and_deadline_enforcement(
    client,
    db_session: Session,
    auth_headers,
    active_conference,
    expired_conference,
    valid_pdf_bytes: bytes,
):
    author_hdrs = auth_headers("alice")

    # 1. Valid submission before conferences.submission_deadline -> 201 Created
    response = client.post(
        "/submissions",
        headers=author_hdrs,
        data={
            "conference_id": str(active_conference.id),
            "title": "Secure Neural Machine Translation",
            "abstract": "A modular transformer system with double-blind security guarantees.",
            "co_authors": json.dumps(
                [{"name": "Bob Jones", "email": "bob.jones@uva.nl", "affiliation": "UvA"}]
            ),
        },
        files={"file": ("paper.pdf", valid_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    submission_id = uuid.UUID(response.json()["id"])

    # Verify persistence across submissions and co_authors tables + stored file
    submission_row = db_session.get(Submission, submission_id)
    assert submission_row is not None
    assert submission_row.status == SubmissionStatus.submitted
    assert submission_row.conference_id == active_conference.id
    assert Path(submission_row.file_path).is_file()

    co_authors = db_session.exec(
        select(CoAuthor).where(CoAuthor.submission_id == submission_id)
    ).all()
    assert len(co_authors) == 1
    assert co_authors[0].email == "bob.jones@uva.nl"

    # Author can query status of their submission (US-05)
    status_resp = client.get(f"/submissions/{submission_id}", headers=author_hdrs)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == SubmissionStatus.submitted.value

    # 2. Late submission after conferences.submission_deadline -> rejected (NFR-03)
    late_resp = client.post(
        "/submissions",
        headers=author_hdrs,
        data={
            "conference_id": str(expired_conference.id),
            "title": "Late Submission Paper",
            "abstract": "Submitted after deadline.",
        },
        files={"file": ("late.pdf", valid_pdf_bytes, "application/pdf")},
    )
    assert late_resp.status_code in (400, 403)

    late_rows = db_session.exec(
        select(Submission).where(Submission.conference_id == expired_conference.id)
    ).all()
    assert len(late_rows) == 0


# =============================================================================
# IT-02 (Functional + AI Privacy): AI Reviewer Matching & Human-in-the-Loop
# SRS Traceability: US-21, FR-06, NFR-04, NFR-07, SEC-05
# Components: FastAPI (AI Module) <-> Database <-> External AI Provider (mocked)
# =============================================================================
@pytest.mark.integration
@pytest.mark.functional
def test_it02_ai_reviewer_matching_strips_pii_and_keeps_human_control(
    client,
    db_session: Session,
    auth_headers,
    seeded_users,
    seeded_submission,
):
    organizer_hdrs = auth_headers("diana")
    captured_payload: dict = {}

    def _fake_recommend_reviewers(submission: dict, candidate_reviewers: list[dict]) -> list[dict]:
        captured_payload["submission"] = submission
        captured_payload["candidate_reviewers"] = candidate_reviewers
        return [
            {
                "reviewer_id": str(seeded_users["charlie"]["id"]),
                "score": 0.94,
                "status": "recommended",
                "confirmed": False,
            },
            {
                "reviewer_id": str(seeded_users["dave"]["id"]),
                "score": 0.21,
                "status": "recommended",
                "confirmed": False,
            },
        ]

    with ExitStack() as stack:
        if importlib.util.find_spec("app.ai.service") is not None:
            stack.enter_context(
                patch(
                    "app.ai.service.recommend_reviewers",
                    side_effect=_fake_recommend_reviewers,
                )
            )
        resp = client.post(
            f"/conferences/{seeded_submission['conference_id']}/submissions/{seeded_submission['id']}/ai-match",
            headers=organizer_hdrs,
        )

    assert resp.status_code == 200
    recommendations = resp.json()["recommendations"]
    assert len(recommendations) >= 1
    assert str(recommendations[0]["reviewer_id"]) == str(seeded_users["charlie"]["id"])

    # SEC-05: Outbound payload to AI component/provider must not contain author PII
    serialized_payload = json.dumps(captured_payload, default=str)
    assert seeded_submission["author_email"] not in serialized_payload
    assert seeded_submission["author_name"] not in serialized_payload
    assert "University of Amsterdam" not in serialized_payload

    # NFR-04: AI provides recommendations only; reviews table must remain untouched
    assigned_rows = db_session.exec(
        select(Review).where(Review.submission_id == seeded_submission["id"])
    ).all()
    assert len(assigned_rows) == 0


# =============================================================================
# IT-03 (Security): RBAC Enforcement & Conflict-of-Interest (COI) Prevention
# SRS Traceability: US-14, US-20, FR-05, NFR-01, SEC-03
# Components: FastAPI (Auth/RBAC + Reviews) <-> Database (user_roles, submissions, co_authors, reviews)
# =============================================================================
@pytest.mark.integration
@pytest.mark.security
def test_it03_rbac_blocks_decision_and_coi_blocks_self_review(
    client,
    db_session: Session,
    auth_headers,
    seeded_submission,
):
    # A. Privilege escalation: Reviewer attempts to record a final editorial decision
    reviewer_hdrs = auth_headers("charlie")
    resp_rbac = client.post(
        f"/submissions/{seeded_submission['id']}/decision",
        headers=reviewer_hdrs,
        json={"status": SubmissionStatus.accepted.value},
    )
    assert resp_rbac.status_code == 403

    db_session.expire_all()
    sub_in_db = db_session.get(Submission, seeded_submission["id"])
    assert sub_in_db is not None
    assert sub_in_db.status == SubmissionStatus.submitted

    # B. Conflict of Interest: Organizer cannot assign primary author OR co-author as reviewer
    organizer_hdrs = auth_headers("diana")
    for conflicted_user_id in (seeded_submission["author_id"], seeded_submission["co_author_id"]):
        resp_coi = client.post(
            f"/submissions/{seeded_submission['id']}/assign",
            headers=organizer_hdrs,
            json={"reviewer_id": str(conflicted_user_id)},
        )
        assert resp_coi.status_code in (400, 403)

    review_rows = db_session.exec(
        select(Review).where(Review.submission_id == seeded_submission["id"])
    ).all()
    assert len(review_rows) == 0


# =============================================================================
# IT-04 (Security): Double-Blind Anonymity, IDOR Isolation & Pre-Release Lock
# SRS Traceability: US-06, US-08, US-09, FR-03, NFR-01, SEC-02, SEC-03
# Components: FastAPI (Reviews/Submissions) <-> Auth/RBAC <-> PDF Storage <-> Database
# =============================================================================
@pytest.mark.integration
@pytest.mark.security
def test_it04_double_blind_anonymity_idor_and_notification_deadline(
    client,
    auth_headers,
    seeded_assigned_submission,
):
    sub_id = seeded_assigned_submission["id"]
    assigned_hdrs = auth_headers(seeded_assigned_submission["assigned_reviewer_key"])
    unassigned_hdrs = auth_headers(seeded_assigned_submission["unassigned_reviewer_key"])
    author_hdrs = auth_headers("alice")

    # A. Assigned reviewer sees anonymized metadata & PDF stripped of author identifiers (SEC-02)
    meta_resp = client.get(f"/reviews/submissions/{sub_id}", headers=assigned_hdrs)
    assert meta_resp.status_code == 200
    meta_body = meta_resp.json()
    assert "author_id" not in meta_body
    assert "co_authors" not in meta_body
    assert seeded_assigned_submission["author_name"] not in meta_resp.text
    assert seeded_assigned_submission["author_email"] not in meta_resp.text

    pdf_resp = client.get(f"/reviews/submissions/{sub_id}/pdf", headers=assigned_hdrs)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")
    assert seeded_assigned_submission["author_name"].encode("utf-8") not in pdf_resp.content

    # B. IDOR: Unassigned reviewer is strictly blocked from accessing submission or PDF (SEC-03)
    idor_resp = client.get(f"/reviews/submissions/{sub_id}/pdf", headers=unassigned_hdrs)
    assert idor_resp.status_code == 403

    # C. Pre-release lock: Author cannot view reviews before conferences.notification_deadline
    early_resp = client.get(f"/submissions/{sub_id}/reviews", headers=author_hdrs)
    assert early_resp.status_code == 403


# =============================================================================
# IT-05 (Security): Secure File Upload, Session Integrity & Invitation Tokens
# SRS Traceability: US-01, US-03, US-13, FR-01, FR-02, NFR-02, SEC-01, SEC-04
# Components: FastAPI (Auth, Invitations, Submissions) <-> File Validator <-> Storage <-> Database
# =============================================================================
@pytest.mark.integration
@pytest.mark.security
def test_it05_malicious_upload_rejected_and_invalid_invitation_blocked(
    client,
    db_session: Session,
    auth_headers,
    active_conference,
    seeded_expired_invitation,
    upload_dir: Path,
):
    author_hdrs = auth_headers("alice")
    files_before = set(upload_dir.iterdir())

    # A. Spoofed PDF upload: Content-Type claims PDF, but payload lacks %PDF- magic bytes (SEC-04)
    malicious_payload = b"#!/bin/sh\ncat /etc/passwd\n"
    resp_upload = client.post(
        "/submissions",
        headers=author_hdrs,
        data={
            "conference_id": str(active_conference.id),
            "title": "Malicious Disguised Upload",
            "abstract": "Attempting to bypass file upload validation.",
        },
        files={"file": ("exploit.pdf", malicious_payload, "application/pdf")},
    )
    assert resp_upload.status_code in (400, 422)

    # Confirm zero persistence in database and zero files written to upload directory
    malicious_rows = db_session.exec(
        select(Submission).where(Submission.title == "Malicious Disguised Upload")
    ).all()
    assert len(malicious_rows) == 0
    assert set(upload_dir.iterdir()) == files_before

    # B. Forged / expired JWT session is rejected before hitting protected workflows (SEC-01)
    expired_hdrs = auth_headers("alice", expired=True)
    resp_expired_jwt = client.post(
        "/submissions",
        headers=expired_hdrs,
        data={
            "conference_id": str(active_conference.id),
            "title": "Expired Session Paper",
            "abstract": "Should not authenticate.",
        },
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert resp_expired_jwt.status_code == 401

    # C. Tampered or expired invitation token cannot be accepted or grant a role
    for candidate_token in ("tampered-invalid-token", seeded_expired_invitation["raw_token"]):
        resp_inv = client.post(
            "/invitations/accept",
            headers=author_hdrs,
            json={"token": candidate_token},
        )
        assert resp_inv.status_code in (400, 401, 403)

    db_session.expire_all()
    inv = db_session.get(Invitation, seeded_expired_invitation["id"])
    assert inv is not None
    assert inv.status == InvitationStatus.invited
