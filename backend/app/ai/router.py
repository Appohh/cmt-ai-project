"""AIReviewMatchComponent HTTP endpoint: PII-stripped AI reviewer recommendations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.ai import service as ai_service
from app.ai.providers import get_matching_provider
from app.ai.schemas import AIMatchResponse, ReviewerRecommendationPublic
from app.core.database import SessionDep
from app.core.logging import log_action
from app.core.security import AuthenticatedUser, require_roles
from app.models.models import (
    CoAuthor,
    Conference,
    InvitationStatus,
    Review,
    Role,
    Submission,
    User,
    UserRole,
)

router = APIRouter(tags=["ai"])


@router.post(
    "/conferences/{conf_id}/submissions/{sub_id}/ai-match",
    response_model=AIMatchResponse,
)
def match_reviewers_for_submission(
    conf_id: uuid.UUID,
    sub_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Recommend ranked reviewers for a paper without sending PII or auto-assigning."""
    conference = session.get(Conference, conf_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    submission = session.get(Submission, sub_id)
    if submission is None or submission.conference_id != conference.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    co_authors = session.exec(
        select(CoAuthor).where(CoAuthor.submission_id == submission.id)
    ).all()
    conflicted_emails = {ca.email.strip().lower() for ca in co_authors if ca.email}

    reviewer_role_rows = session.exec(
        select(UserRole).where(UserRole.role == Role.reviewer)
    ).all()
    reviewer_ids = {row.user_id for row in reviewer_role_rows}

    candidate_users: dict[str, User] = {}
    candidate_payload: list[dict] = []
    for uid in reviewer_ids:
        if uid == submission.author_id:
            continue
        user = session.get(User, uid)
        if user is None:
            continue
        if user.email.strip().lower() in conflicted_emails:
            continue
        uid_str = str(user.id)
        candidate_users[uid_str] = user
        # SEC-05: Send only non-identifying ID and expertise text to AI component/provider
        candidate_payload.append(
            {
                "reviewer_id": uid_str,
                "expertise": user.expertise or "",
            }
        )

    # SEC-05: Submission payload omits author_id, author_name, author_email, affiliation, co_authors
    submission_payload = {
        "id": str(submission.id),
        "title": submission.title,
        "abstract": submission.abstract,
    }

    provider_name, _ = get_matching_provider()
    raw_recommendations = ai_service.recommend_reviewers(submission_payload, candidate_payload)

    existing_sub_reviews = session.exec(
        select(Review).where(
            Review.submission_id == submission.id,
            Review.status != InvitationStatus.declined,
        )
    ).all()
    assigned_reviewer_ids = {str(r.reviewer_id) for r in existing_sub_reviews}

    all_active_reviews = session.exec(
        select(Review).where(Review.status != InvitationStatus.declined)
    ).all()
    active_count_by_reviewer: dict[str, int] = {}
    for r in all_active_reviews:
        rid = str(r.reviewer_id)
        active_count_by_reviewer[rid] = active_count_by_reviewer.get(rid, 0) + 1

    enriched: list[ReviewerRecommendationPublic] = []
    for rec in raw_recommendations:
        rid = str(rec["reviewer_id"])
        user = candidate_users.get(rid)
        if user is None:
            uid_obj = uuid.UUID(rid)
            user = session.get(User, uid_obj)
        enriched.append(
            ReviewerRecommendationPublic(
                reviewer_id=rid,
                score=float(rec["score"]),
                status=str(rec.get("status", "recommended")),
                confirmed=bool(rec.get("confirmed", False)),
                name=f"{user.first_name} {user.last_name}" if user else None,
                affiliation=user.affiliation if user else None,
                expertise=user.expertise if user else None,
                active_reviews=active_count_by_reviewer.get(rid, 0),
                already_assigned=rid in assigned_reviewer_ids,
            )
        )

    log_action(
        "ai.match_requested",
        actor_id=auth.user.id,
        target_id=submission.id,
        details={"provider": provider_name, "candidates": len(candidate_payload)},
    )
    return AIMatchResponse(
        submission_id=submission.id,
        provider=provider_name,
        recommendations=enriched,
    )
