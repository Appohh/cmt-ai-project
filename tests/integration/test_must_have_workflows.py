"""Additional integration tests covering remaining Must-Have workflows."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import pytest
from sqlmodel import Session

from app.core.config import utcnow
from app.models.models import Conference, Invitation, InvitationStatus, Role, SubmissionStatus


@pytest.mark.integration
@pytest.mark.security
def test_auth_register_login_and_logout_revocation(client):
    """US-01 / SEC-01: Register, login, and verify logout revokes active JWT jti."""
    reg_resp = client.post(
        "/auth/register",
        json={
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "GRACE@Example.com",
            "password": "StrongPassword123!",
            "affiliation": "Yale University",
            "expertise": "Compilers, security",
        },
    )
    assert reg_resp.status_code == 201
    reg_body = reg_resp.json()
    assert reg_body["user"]["email"] == "grace@example.com"
    assert reg_body["user"]["roles"] == ["author"]

    login_resp = client.post(
        "/auth/login",
        json={"email": "grace@example.com", "password": "StrongPassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    hdrs = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/auth/me", headers=hdrs)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "grace@example.com"

    logout_resp = client.post("/auth/logout", headers=hdrs)
    assert logout_resp.status_code == 200

    revoked_resp = client.get("/auth/me", headers=hdrs)
    assert revoked_resp.status_code == 401


@pytest.mark.integration
@pytest.mark.functional
def test_profile_update_and_password_change(client, auth_headers):
    """US-02: User updates personal info and changes password."""
    hdrs = auth_headers("alice")
    patch_resp = client.patch(
        "/users/me",
        headers=hdrs,
        json={"affiliation": "Vrije Universiteit", "expertise": "Privacy, NMT"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["affiliation"] == "Vrije Universiteit"

    reg = client.post(
        "/auth/register",
        json={
            "first_name": "Test",
            "last_name": "User",
            "email": "pwchange@example.com",
            "password": "OldPassword123!",
        },
    ).json()
    user_hdrs = {"Authorization": f"Bearer {reg['access_token']}"}
    pw_resp = client.post(
        "/users/me/password",
        headers=user_hdrs,
        json={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
    )
    assert pw_resp.status_code == 200

    new_login = client.post(
        "/auth/login",
        json={"email": "pwchange@example.com", "password": "NewPassword456!"},
    )
    assert new_login.status_code == 200


@pytest.mark.integration
@pytest.mark.functional
def test_submission_edit_and_withdraw_before_deadline(
    client,
    auth_headers,
    active_conference: Conference,
    valid_pdf_bytes: bytes,
):
    """US-04: Author edits and withdraws a submission before the submission deadline."""
    hdrs = auth_headers("alice")
    create_resp = client.post(
        "/submissions",
        headers=hdrs,
        data={
            "conference_id": str(active_conference.id),
            "title": "Initial Draft Title",
            "abstract": "Initial draft abstract.",
        },
        files={"file": ("draft.pdf", valid_pdf_bytes, "application/pdf")},
    )
    assert create_resp.status_code == 201
    sub_id = create_resp.json()["id"]

    edit_resp = client.put(
        f"/submissions/{sub_id}",
        headers=hdrs,
        data={
            "title": "Updated Paper Title",
            "abstract": "Updated abstract with clearer results.",
        },
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["title"] == "Updated Paper Title"

    withdraw_resp = client.post(f"/submissions/{sub_id}/withdraw", headers=hdrs)
    assert withdraw_resp.status_code == 200
    assert withdraw_resp.json()["status"] == SubmissionStatus.withdrawn.value


@pytest.mark.integration
@pytest.mark.functional
def test_reviewer_accept_submit_and_chair_progress(
    client,
    auth_headers,
    seeded_users,
    seeded_submission,
):
    """US-07 / US-10 / US-15 / US-18: Reviewer accepts, scores paper, and Chair sees average."""
    organizer_hdrs = auth_headers("diana")
    reviewer_hdrs = auth_headers("charlie")

    assign_resp = client.post(
        f"/submissions/{seeded_submission['id']}/assign",
        headers=organizer_hdrs,
        json={"reviewer_id": str(seeded_users["charlie"]["id"])},
    )
    assert assign_resp.status_code == 201
    review_id = assign_resp.json()["id"]

    accept_resp = client.post(
        f"/reviews/{review_id}/respond",
        headers=reviewer_hdrs,
        json={"status": "accepted"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"

    score_resp = client.put(
        f"/reviews/{review_id}",
        headers=reviewer_hdrs,
        json={
            "score": 4,
            "confidence": 5,
            "comments": "Solid double-blind privacy guarantees.",
        },
    )
    assert score_resp.status_code == 200
    assert score_resp.json()["score"] == 4

    chair_resp = client.get(
        f"/conferences/{seeded_submission['conference_id']}/submissions",
        headers=organizer_hdrs,
    )
    assert chair_resp.status_code == 200
    body = chair_resp.json()
    assert body["summary"]["completed_reviews"] == 1
    assert body["submissions"][0]["average_score"] == pytest.approx(4.0)


@pytest.mark.integration
@pytest.mark.security
def test_conference_creation_valid_invitation_and_admin_rbac(
    client,
    db_session: Session,
    auth_headers,
    active_conference: Conference,
):
    """US-11 / US-13 / US-19 / US-20: Conference deadlines, invite redemption, and admin RBAC."""
    organizer_hdrs = auth_headers("diana")
    now = utcnow()

    bad_conf = client.post(
        "/conferences/",
        headers=organizer_hdrs,
        json={
            "name": "Invalid Order Conf",
            "submission_deadline": (now + timedelta(days=10)).isoformat(),
            "review_deadline": (now + timedelta(days=5)).isoformat(),
            "notification_deadline": (now + timedelta(days=20)).isoformat(),
        },
    )
    assert bad_conf.status_code == 400

    good_conf = client.post(
        "/conferences/",
        headers=organizer_hdrs,
        json={
            "name": "EAMT 2029",
            "description": "Next year conference",
            "submission_deadline": (now + timedelta(days=10)).isoformat(),
            "review_deadline": (now + timedelta(days=20)).isoformat(),
            "notification_deadline": (now + timedelta(days=30)).isoformat(),
        },
    )
    assert good_conf.status_code == 201

    inv_resp = client.post(
        f"/conferences/{active_conference.id}/invitations",
        headers=organizer_hdrs,
        json={"email": "guest.invite@example.com", "role": "guest"},
    )
    assert inv_resp.status_code == 201
    raw_token = inv_resp.json()["raw_token"]

    accept_resp = client.post(
        "/invitations/accept",
        headers=auth_headers("alice"),
        json={"token": raw_token},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["role_granted"] == "guest"

    inv_row = db_session.get(Invitation, uuid.UUID(inv_resp.json()["invitation"]["id"]))
    assert inv_row is not None
    assert inv_row.status == InvitationStatus.accepted
    assert inv_row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Non-admin user cannot access Admin overview
    forbidden_admin = client.get("/admin/overview", headers=auth_headers("alice"))
    assert forbidden_admin.status_code == 403
