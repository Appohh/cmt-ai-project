"""AIReviewMatchComponent HTTP endpoints: AI reviewer matching, topic tags & provider config."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.ai import service as ai_service
from app.ai.providers import (
    VALID_AI_PROVIDERS,
    check_ollama_reachable,
    get_matching_provider,
    get_runtime_ai_settings,
    update_runtime_ai_settings,
)
from app.ai.schemas import (
    AIMatchResponse,
    AIProviderStatusResponse,
    AIProviderUpdateRequest,
    BulkTagsResponse,
    EntityTagsResponse,
    ReviewerRecommendationPublic,
)
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
    TopicTag,
    User,
    UserRole,
)

router = APIRouter(tags=["ai"])


def _replace_entity_tags(
    session: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    tags: list[str],
) -> list[str]:
    existing = session.exec(
        select(TopicTag).where(
            TopicTag.entity_type == entity_type,
            TopicTag.entity_id == entity_id,
        )
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()

    for tag in tags:
        session.add(TopicTag(entity_type=entity_type, entity_id=entity_id, tag=tag))
    session.commit()
    return tags


def _build_provider_status() -> AIProviderStatusResponse:
    settings = get_runtime_ai_settings()
    return AIProviderStatusResponse(
        active_provider=settings["provider"],
        available_providers=list(VALID_AI_PROVIDERS),
        ollama_base_url=settings["ollama_base_url"],
        ollama_model=settings["ollama_model"],
        ollama_reachable=check_ollama_reachable(settings["ollama_base_url"]),
        gemini_model=settings["gemini_model"],
        gemini_configured=settings["gemini_configured"],
        openai_model=settings["openai_model"],
        openai_configured=settings["openai_configured"],
    )


@router.get("/ai/providers", response_model=AIProviderStatusResponse)
def get_ai_providers(
    _auth: AuthenticatedUser = Depends(require_roles(Role.organizer, Role.admin)),
):
    """Return active LLMProviderComponent configuration and local Ollama availability."""
    return _build_provider_status()


@router.patch("/ai/providers", response_model=AIProviderStatusResponse)
def update_ai_providers(
    payload: AIProviderUpdateRequest,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer, Role.admin)),
):
    """Switch active AI provider (local, ollama, gemini, openai) or update model settings."""
    try:
        update_runtime_ai_settings(
            provider=payload.provider,
            ollama_base_url=payload.ollama_base_url,
            ollama_model=payload.ollama_model,
            gemini_api_key=payload.gemini_api_key,
            gemini_model=payload.gemini_model,
            openai_api_key=payload.openai_api_key,
            openai_model=payload.openai_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    log_action(
        "ai.provider_updated",
        actor_id=auth.user.id,
        details={"provider": payload.provider, "ollama_model": payload.ollama_model, "gemini_model": payload.gemini_model},
    )
    return _build_provider_status()


@router.post(
    "/conferences/{conf_id}/submissions/{sub_id}/ai-match",
    response_model=AIMatchResponse,
)
def match_reviewers_for_submission(
    conf_id: uuid.UUID,
    sub_id: uuid.UUID,
    session: SessionDep,
    provider: str | None = Query(default=None),
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

    if provider and provider.strip().lower() in VALID_AI_PROVIDERS:
        update_runtime_ai_settings(provider=provider.strip().lower())

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

    reviewer_tag_rows = session.exec(
        select(TopicTag).where(TopicTag.entity_type == "reviewer")
    ).all()
    tags_by_reviewer: dict[str, list[str]] = {}
    for row in reviewer_tag_rows:
        tags_by_reviewer.setdefault(str(row.entity_id), []).append(row.tag)

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
                topic_tags=tags_by_reviewer.get(rid, []),
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


@router.post("/ai/submissions/{sub_id}/tags", response_model=EntityTagsResponse)
def generate_submission_tags(
    sub_id: uuid.UUID,
    session: SessionDep,
    provider: str | None = Query(default=None),
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Generate and persist AI topic tags for a submission using PII-free title & abstract."""
    submission = session.get(Submission, sub_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    provider_name, tags = ai_service.generate_topic_tags(
        f"{submission.title}\n{submission.abstract}",
        max_tags=4,
        provider_override=provider,
    )
    _replace_entity_tags(session, "submission", submission.id, tags)
    log_action(
        "ai.submission_tags_generated",
        actor_id=auth.user.id,
        target_id=submission.id,
        details={"provider": provider_name, "count": len(tags)},
    )
    return EntityTagsResponse(
        entity_type="submission",
        entity_id=submission.id,
        provider=provider_name,
        tags=tags,
    )


@router.post("/ai/reviewers/{user_id}/tags", response_model=EntityTagsResponse)
def generate_reviewer_tags(
    user_id: uuid.UUID,
    session: SessionDep,
    provider: str | None = Query(default=None),
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Generate and persist AI topic tags for a reviewer profile using expertise only."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    provider_name, tags = ai_service.generate_topic_tags(
        user.expertise or "",
        max_tags=4,
        provider_override=provider,
    )
    _replace_entity_tags(session, "reviewer", user.id, tags)
    log_action(
        "ai.reviewer_tags_generated",
        actor_id=auth.user.id,
        target_id=user.id,
        details={"provider": provider_name, "count": len(tags)},
    )
    return EntityTagsResponse(
        entity_type="reviewer",
        entity_id=user.id,
        provider=provider_name,
        tags=tags,
    )


@router.post("/conferences/{conf_id}/ai-tags/generate-all", response_model=BulkTagsResponse)
def generate_all_conference_tags(
    conf_id: uuid.UUID,
    session: SessionDep,
    provider: str | None = Query(default=None),
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Generate AI topic tags for all submissions and committee reviewers in a conference."""
    conference = session.get(Conference, conf_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    submissions = session.exec(
        select(Submission).where(Submission.conference_id == conf_id)
    ).all()
    reviewer_rows = session.exec(
        select(UserRole).where(UserRole.role == Role.reviewer)
    ).all()
    reviewer_ids = {row.user_id for row in reviewer_rows}

    batch_items: list[dict[str, str]] = []
    sub_by_key: dict[str, Submission] = {}
    rev_by_key: dict[str, User] = {}

    for sub in submissions:
        key = f"sub:{sub.id}"
        sub_by_key[key] = sub
        batch_items.append({"id": key, "text": f"{sub.title}\n{sub.abstract}"})

    for uid in reviewer_ids:
        user = session.get(User, uid)
        if user is None or not (user.expertise or "").strip():
            continue
        key = f"rev:{user.id}"
        rev_by_key[key] = user
        batch_items.append({"id": key, "text": user.expertise or ""})

    used_provider, tag_map = ai_service.generate_bulk_topic_tags(
        batch_items,
        max_tags=4,
        provider_override=provider,
    )

    for key, sub in sub_by_key.items():
        _replace_entity_tags(session, "submission", sub.id, tag_map.get(key, []))

    for key, user in rev_by_key.items():
        _replace_entity_tags(session, "reviewer", user.id, tag_map.get(key, []))

    sub_count = len(sub_by_key)
    rev_count = len(rev_by_key)

    log_action(
        "ai.bulk_tags_generated",
        actor_id=auth.user.id,
        target_id=conference.id,
        details={"provider": used_provider, "submissions": sub_count, "reviewers": rev_count},
    )
    return BulkTagsResponse(
        conference_id=conference.id,
        provider=used_provider,
        submissions_tagged=sub_count,
        reviewers_tagged=rev_count,
    )
