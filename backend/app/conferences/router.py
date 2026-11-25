"""ConferenceComponent & Invitation HTTP endpoints."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.auth.service import get_user_roles
from app.conferences import service as conferences_service
from app.conferences.schemas import (
    ChairProgressSummary,
    ChairReviewBrief,
    ChairSubmissionItem,
    ChairSubmissionsResponse,
    CommitteeMemberPublic,
    ConferenceCommitteeResponse,
    ConferenceCreate,
    ConferencePublic,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationPublic,
)
from app.core.config import ensure_utc, get_frontend_base_url, utcnow
from app.core.database import SessionDep
from app.core.logging import log_action
from app.core.security import AuthenticatedUser, get_current_user, require_roles
from app.models.models import (
    CoAuthor,
    Conference,
    Invitation,
    InvitationStatus,
    Review,
    Role,
    Submission,
    TopicTag,
    User,
    UserRole,
)
from app.notifications.service import send_invitation_notification
from app.reviews.service import calculate_average_score

router = APIRouter(prefix="/conferences", tags=["conferences"])
invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/", response_model=list[ConferencePublic])
@router.get("", response_model=list[ConferencePublic], include_in_schema=False)
def list_conferences(session: SessionDep):
    """List all configured conferences."""
    return session.exec(select(Conference).order_by(Conference.submission_deadline.desc())).all()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ConferencePublic)
@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConferencePublic, include_in_schema=False)
def create_conference_endpoint(
    payload: ConferenceCreate,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer, Role.admin)),
):
    """Create a new conference after validating chronological deadline ordering."""
    try:
        validated = conferences_service.create_conference(
            name=payload.name,
            description=payload.description or "",
            submission_deadline=payload.submission_deadline,
            review_deadline=payload.review_deadline,
            notification_deadline=payload.notification_deadline,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    conference = Conference(
        name=validated["name"],
        description=validated["description"],
        submission_deadline=validated["submission_deadline"],
        review_deadline=validated["review_deadline"],
        notification_deadline=validated["notification_deadline"],
    )
    session.add(conference)
    session.commit()
    session.refresh(conference)

    log_action("conference.created", actor_id=auth.user.id, target_id=conference.id)
    return conference


@router.get("/{conf_id}/submissions", response_model=ChairSubmissionsResponse)
def get_conference_submissions(
    conf_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),  # noqa: ARG001
):
    """Organizer overview of all submissions, assigned reviewers, scores, and progress."""
    conference = session.get(Conference, conf_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    submissions = session.exec(
        select(Submission)
        .where(Submission.conference_id == conf_id)
        .order_by(Submission.created_at.desc())
    ).all()

    user_cache: dict[uuid.UUID, User | None] = {}

    def _get_user(uid: uuid.UUID) -> User | None:
        if uid not in user_cache:
            user_cache[uid] = session.get(User, uid)
        return user_cache[uid]

    total_reviews = 0
    completed_reviews = 0
    unassigned_papers = 0
    items: list[ChairSubmissionItem] = []

    sub_tag_rows = session.exec(
        select(TopicTag).where(TopicTag.entity_type == "submission")
    ).all()
    tags_by_sub: dict[uuid.UUID, list[str]] = {}
    for trow in sub_tag_rows:
        tags_by_sub.setdefault(trow.entity_id, []).append(trow.tag)

    for sub in submissions:
        author = _get_user(sub.author_id)
        author_name = f"{author.first_name} {author.last_name}" if author else "Unknown Author"
        co_authors = session.exec(
            select(CoAuthor).where(CoAuthor.submission_id == sub.id)
        ).all()
        reviews = session.exec(
            select(Review).where(Review.submission_id == sub.id)
        ).all()

        active_reviews = [r for r in reviews if r.status != InvitationStatus.declined]
        if not active_reviews:
            unassigned_papers += 1

        total_reviews += len(active_reviews)
        scored = [r for r in active_reviews if r.score is not None]
        completed_reviews += len(scored)

        avg_score: float | None = None
        if scored:
            avg_score = round(
                calculate_average_score([{"score": r.score} for r in scored]),
                2,
            )

        review_briefs: list[ChairReviewBrief] = []
        for r in active_reviews:
            reviewer = _get_user(r.reviewer_id)
            reviewer_name = (
                f"{reviewer.first_name} {reviewer.last_name}" if reviewer else "Reviewer"
            )
            review_briefs.append(
                ChairReviewBrief(
                    review_id=r.id,
                    reviewer_id=r.reviewer_id,
                    reviewer_name=reviewer_name,
                    status=r.status.value,
                    score=r.score,
                    confidence=r.confidence,
                    comments=r.comments,
                )
            )

        items.append(
            ChairSubmissionItem(
                id=sub.id,
                title=sub.title,
                abstract=sub.abstract,
                author_id=sub.author_id,
                author_name=author_name,
                co_author_names=[ca.name for ca in co_authors],
                status=sub.status.value,
                average_score=avg_score,
                topic_tags=tags_by_sub.get(sub.id, []),
                reviews=review_briefs,
            )
        )

    summary = ChairProgressSummary(
        completed_reviews=completed_reviews,
        total_reviews=total_reviews,
        missing_reviews=total_reviews - completed_reviews,
        unassigned_papers=unassigned_papers,
    )
    return ChairSubmissionsResponse(
        conference_id=conf_id,
        summary=summary,
        submissions=items,
    )


@router.get("/{conf_id}/committee", response_model=ConferenceCommitteeResponse)
def get_conference_committee(
    conf_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),  # noqa: ARG001
):
    """List programme committee members (reviewers/guests) and pending invitations."""
    conference = session.get(Conference, conf_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    all_role_rows = session.exec(select(UserRole)).all()
    roles_by_user: dict[uuid.UUID, list[Role]] = {}
    for row in all_role_rows:
        roles_by_user.setdefault(row.user_id, []).append(row.role)

    committee_ids = [
        uid
        for uid, roles in roles_by_user.items()
        if Role.reviewer in roles or Role.guest in roles
    ]

    conf_sub_ids = {
        sub.id
        for sub in session.exec(select(Submission).where(Submission.conference_id == conf_id)).all()
    }
    conf_reviews = (
        session.exec(select(Review).where(Review.submission_id.in_(list(conf_sub_ids)))).all()  # type: ignore[attr-defined]
        if conf_sub_ids
        else []
    )

    reviewer_tag_rows = session.exec(
        select(TopicTag).where(TopicTag.entity_type == "reviewer")
    ).all()
    tags_by_reviewer: dict[uuid.UUID, list[str]] = {}
    for trow in reviewer_tag_rows:
        tags_by_reviewer.setdefault(trow.entity_id, []).append(trow.tag)

    members: list[CommitteeMemberPublic] = []
    for uid in committee_ids:
        user = session.get(User, uid)
        if user is None:
            continue
        user_reviews = [
            r
            for r in conf_reviews
            if r.reviewer_id == uid and r.status != InvitationStatus.declined
        ]
        completed = sum(1 for r in user_reviews if r.score is not None)
        members.append(
            CommitteeMemberPublic(
                id=user.id,
                name=f"{user.first_name} {user.last_name}",
                email=user.email,
                affiliation=user.affiliation,
                expertise=user.expertise,
                topic_tags=tags_by_reviewer.get(user.id, []),
                roles=sorted(r.value for r in roles_by_user.get(uid, [])),
                completed_reviews=completed,
                total_assigned=len(user_reviews),
            )
        )
    members.sort(key=lambda m: m.name.lower())

    invitations = session.exec(
        select(Invitation)
        .where(Invitation.conference_id == conf_id)
        .order_by(Invitation.created_at.desc())
    ).all()
    invitation_items = [
        InvitationPublic(
            id=inv.id,
            email=inv.email,
            role=inv.role.value,
            status=inv.status.value,
            expires_at=inv.expires_at,
        )
        for inv in invitations
    ]

    return ConferenceCommitteeResponse(members=members, invitations=invitation_items)


@router.post(
    "/{conf_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationCreatedResponse,
)
def create_conference_invitation(
    conf_id: uuid.UUID,
    payload: InvitationCreate,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Invite a reviewer or guest to the conference with a SHA-256 hashed expiring token."""
    conference = session.get(Conference, conf_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    normalized_email = payload.email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid recipient email is required",
        )

    raw_token, token_hash = conferences_service.generate_invitation_token()
    expires_at = utcnow() + timedelta(days=7)

    invitation = Invitation(
        conference_id=conference.id,
        email=normalized_email,
        role=Role(payload.role),
        status=InvitationStatus.invited,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(invitation)
    session.commit()
    session.refresh(invitation)

    invite_link = f"{get_frontend_base_url()}/?invite={raw_token}"
    send_invitation_notification(normalized_email, conference.name, payload.role, invite_link)
    log_action(
        "invitation.created",
        actor_id=auth.user.id,
        target_id=invitation.id,
        details={"conference_id": str(conference.id), "role": payload.role},
    )

    return InvitationCreatedResponse(
        invitation=InvitationPublic(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role.value,
            status=invitation.status.value,
            expires_at=invitation.expires_at,
        ),
        raw_token=raw_token,
        invite_link=invite_link,
    )


@invitations_router.post("/accept", response_model=InvitationAcceptResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Redeem a conference invitation token and grant the invited role to the caller."""
    raw_token = (payload.token or "").strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token is required",
        )

    token_hash = conferences_service.hash_invitation_token(raw_token)
    invitation = session.exec(
        select(Invitation).where(Invitation.token_hash == token_hash)
    ).first()

    if invitation is None or invitation.status != InvitationStatus.invited:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already redeemed invitation token",
        )

    if utcnow() > ensure_utc(invitation.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired",
        )

    invitation.status = InvitationStatus.accepted
    session.add(invitation)

    existing_role = session.exec(
        select(UserRole).where(
            UserRole.user_id == auth.user.id,
            UserRole.role == invitation.role,
        )
    ).first()
    if existing_role is None:
        session.add(UserRole(user_id=auth.user.id, role=invitation.role))

    session.commit()
    updated_roles = [r.value for r in get_user_roles(session, auth.user.id)]
    log_action(
        "invitation.accepted",
        actor_id=auth.user.id,
        target_id=invitation.id,
        details={"role_granted": invitation.role.value},
    )

    return InvitationAcceptResponse(
        status="accepted",
        role_granted=invitation.role.value,
        conference_id=invitation.conference_id,
        roles=sorted(updated_roles),
    )
