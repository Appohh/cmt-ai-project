"""SubmissionComponent HTTP endpoints: submit, edit, withdraw, PDF, reviews, and decisions."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel import Session, select

from app.core.config import ensure_utc, get_upload_dir, utcnow
from app.core.database import SessionDep
from app.core.logging import log_action
from app.core.security import AuthenticatedUser, get_current_user, require_roles
from app.models.models import (
    CoAuthor,
    Conference,
    InvitationStatus,
    Review,
    Role,
    Submission,
    SubmissionStatus,
    TopicTag,
    User,
)
from app.notifications.service import send_decision_notification
from app.reviews.service import calculate_average_score
from app.submissions.pre_check import check_and_sanitize_pdf
from app.submissions.schemas import (
    CoAuthorIn,
    CoAuthorPublic,
    DecisionRequest,
    ReleasedReviewPublic,
    SubmissionPublic,
    SubmissionReviewsResponse,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _parse_co_authors(raw: str | None) -> list[CoAuthorIn]:
    if not raw or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid co_authors JSON format",
        ) from exc

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="co_authors must be a JSON list",
        )

    items: list[CoAuthorIn] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each co-author must be an object",
            )
        name = str(entry.get("name", "")).strip()
        email = str(entry.get("email", "")).strip().lower()
        aff = entry.get("affiliation")
        affiliation = str(aff).strip() if aff else None
        if not name or not email or "@" not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each co-author requires a valid name and email",
            )
        items.append(CoAuthorIn(name=name, email=email, affiliation=affiliation))
    return items


def _serialize_submission(
    session: Session,
    submission: Submission,
    conference: Conference | None = None,
) -> SubmissionPublic:
    conf = conference or session.get(Conference, submission.conference_id)
    co_author_rows = session.exec(
        select(CoAuthor).where(CoAuthor.submission_id == submission.id)
    ).all()
    tag_rows = session.exec(
        select(TopicTag).where(
            TopicTag.entity_type == "submission",
            TopicTag.entity_id == submission.id,
        )
    ).all()
    now = utcnow()
    decision_released = (
        now >= ensure_utc(conf.notification_deadline) if conf is not None else False
    )
    can_edit = (
        submission.status == SubmissionStatus.submitted
        and conf is not None
        and now <= ensure_utc(conf.submission_deadline)
    )
    return SubmissionPublic(
        id=submission.id,
        conference_id=submission.conference_id,
        conference_name=conf.name if conf else None,
        author_id=submission.author_id,
        title=submission.title,
        abstract=submission.abstract,
        status=submission.status.value,
        co_authors=[
            CoAuthorPublic(
                id=row.id,
                name=row.name,
                email=row.email,
                affiliation=row.affiliation,
            )
            for row in co_author_rows
        ],
        topic_tags=[row.tag for row in tag_rows],
        decision_released=decision_released,
        can_edit=can_edit,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


@router.get("/mine", response_model=list[SubmissionPublic])
def list_my_submissions(
    session: SessionDep,
    conference_id: uuid.UUID | None = None,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """List submissions authored by the authenticated user."""
    query = select(Submission).where(Submission.author_id == auth.user.id)
    if conference_id is not None:
        query = query.where(Submission.conference_id == conference_id)
    submissions = session.exec(query.order_by(Submission.created_at.desc())).all()

    conf_cache: dict[uuid.UUID, Conference | None] = {}
    result: list[SubmissionPublic] = []
    for sub in submissions:
        if sub.conference_id not in conf_cache:
            conf_cache[sub.conference_id] = session.get(Conference, sub.conference_id)
        result.append(_serialize_submission(session, sub, conf_cache[sub.conference_id]))
    return result


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SubmissionPublic)
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SubmissionPublic, include_in_schema=False)
async def create_submission(
    session: SessionDep,
    conference_id: str = Form(...),
    title: str = Form(...),
    abstract: str = Form(...),
    co_authors: str | None = Form(default=None),
    file: UploadFile = File(...),
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Submit a paper with co-authors and a validated, metadata-stripped PDF before deadline."""
    try:
        conf_uuid = uuid.UUID(conference_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conference_id") from exc

    conference = session.get(Conference, conf_uuid)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    if utcnow() > ensure_utc(conference.submission_deadline):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission deadline has passed for this conference",
        )

    clean_title = title.strip()
    clean_abstract = abstract.strip()
    if not clean_title or not clean_abstract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title and abstract are required",
        )

    parsed_co_authors = _parse_co_authors(co_authors)
    raw_bytes = await file.read()
    try:
        clean_pdf_bytes = check_and_sanitize_pdf(
            filename=file.filename or "",
            content_type=file.content_type or "",
            file_bytes=raw_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    sub_id = uuid.uuid4()
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / f"{sub_id}.pdf"
    pdf_path.write_bytes(clean_pdf_bytes)

    submission = Submission(
        id=sub_id,
        conference_id=conference.id,
        author_id=auth.user.id,
        title=clean_title,
        abstract=clean_abstract,
        file_path=str(pdf_path),
        status=SubmissionStatus.submitted,
    )
    session.add(submission)
    session.flush()

    for ca in parsed_co_authors:
        session.add(
            CoAuthor(
                submission_id=submission.id,
                name=ca.name,
                email=ca.email,
                affiliation=ca.affiliation,
            )
        )

    session.commit()
    session.refresh(submission)

    log_action("submission.created", actor_id=auth.user.id, target_id=submission.id)
    return _serialize_submission(session, submission, conference)


@router.get("/{submission_id}", response_model=SubmissionPublic)
def get_submission(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Fetch a submission for its author owner, an organizer, or an administrator."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    is_owner = submission.author_id == auth.user.id
    if not (is_owner or auth.has_role(Role.organizer) or auth.has_role(Role.admin)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this submission",
        )

    return _serialize_submission(session, submission)


@router.put("/{submission_id}", response_model=SubmissionPublic)
async def update_submission(
    submission_id: uuid.UUID,
    session: SessionDep,
    title: str = Form(...),
    abstract: str = Form(...),
    co_authors: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Edit title, abstract, co-authors, or replace the PDF before the submission deadline."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if submission.author_id != auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the submitting author may edit this paper",
        )
    if submission.status != SubmissionStatus.submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawn or decided submissions cannot be edited",
        )

    conference = session.get(Conference, submission.conference_id)
    if conference is None or utcnow() > ensure_utc(conference.submission_deadline):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission deadline has passed",
        )

    clean_title = title.strip()
    clean_abstract = abstract.strip()
    if not clean_title or not clean_abstract:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title and abstract are required",
        )

    parsed_co_authors = _parse_co_authors(co_authors)

    if file is not None and (file.filename or "").strip():
        raw_bytes = await file.read()
        try:
            clean_pdf_bytes = check_and_sanitize_pdf(
                filename=file.filename or "",
                content_type=file.content_type or "",
                file_bytes=raw_bytes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        upload_dir = get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = upload_dir / f"{submission.id}.pdf"
        pdf_path.write_bytes(clean_pdf_bytes)
        submission.file_path = str(pdf_path)

    submission.title = clean_title
    submission.abstract = clean_abstract
    session.add(submission)

    existing_co_authors = session.exec(
        select(CoAuthor).where(CoAuthor.submission_id == submission.id)
    ).all()
    for row in existing_co_authors:
        session.delete(row)
    session.flush()

    for ca in parsed_co_authors:
        session.add(
            CoAuthor(
                submission_id=submission.id,
                name=ca.name,
                email=ca.email,
                affiliation=ca.affiliation,
            )
        )

    session.commit()
    session.refresh(submission)

    log_action("submission.updated", actor_id=auth.user.id, target_id=submission.id)
    return _serialize_submission(session, submission, conference)


@router.post("/{submission_id}/withdraw", response_model=SubmissionPublic)
def withdraw_submission(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Withdraw a paper prior to the conference submission deadline."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if submission.author_id != auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the submitting author may withdraw this paper",
        )
    if submission.status != SubmissionStatus.submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active submitted papers can be withdrawn",
        )

    conference = session.get(Conference, submission.conference_id)
    if conference is None or utcnow() > ensure_utc(conference.submission_deadline):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission deadline has passed",
        )

    submission.status = SubmissionStatus.withdrawn
    session.add(submission)
    session.commit()
    session.refresh(submission)

    log_action("submission.withdrawn", actor_id=auth.user.id, target_id=submission.id)
    return _serialize_submission(session, submission, conference)


@router.get("/{submission_id}/pdf")
def download_submission_pdf(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Allow the submitting author or an organizer to download the stored submission PDF."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if submission.author_id != auth.user.id and not auth.has_role(Role.organizer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to download this PDF",
        )

    pdf_path = Path(submission.file_path)
    if not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return Response(
        content=pdf_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="submission-{submission_id}.pdf"'},
    )


@router.get("/{submission_id}/reviews", response_model=SubmissionReviewsResponse)
def get_submission_reviews(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Return reviews for a submission; authors are blocked until notification_deadline."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    conference = session.get(Conference, submission.conference_id)
    if conference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conference not found")

    is_organizer = auth.has_role(Role.organizer)
    is_owner = submission.author_id == auth.user.id

    if not (is_organizer or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view reviews for this submission",
        )

    if not is_organizer and utcnow() < ensure_utc(conference.notification_deadline):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviews and final decisions are locked until the notification deadline",
        )

    review_rows = session.exec(
        select(Review).where(
            Review.submission_id == submission.id,
            Review.status != InvitationStatus.declined,
        )
    ).all()
    completed = [r for r in review_rows if r.score is not None]

    avg_score: float | None = None
    if completed:
        avg_score = round(
            calculate_average_score([{"score": r.score} for r in completed]),
            2,
        )

    released_reviews: list[ReleasedReviewPublic] = []
    for r in completed:
        reviewer_name: str | None = None
        if is_organizer:
            reviewer = session.get(User, r.reviewer_id)
            if reviewer is not None:
                reviewer_name = f"{reviewer.first_name} {reviewer.last_name}"
        released_reviews.append(
            ReleasedReviewPublic(
                id=r.id,
                score=r.score,
                confidence=r.confidence,
                comments=r.comments,
                reviewer_name=reviewer_name,
            )
        )

    return SubmissionReviewsResponse(
        submission_id=submission.id,
        status=submission.status.value,
        average_score=avg_score,
        reviews=released_reviews,
    )


@router.post("/{submission_id}/decision", response_model=SubmissionPublic)
def record_submission_decision(
    submission_id: uuid.UUID,
    payload: DecisionRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Record an organizer's final acceptance or rejection decision for a submission."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    submission.status = SubmissionStatus(payload.status)
    session.add(submission)
    session.commit()
    session.refresh(submission)

    author = session.get(User, submission.author_id)
    if author is not None:
        send_decision_notification(author.email, submission.title, submission.status.value)

    log_action(
        "submission.decision_recorded",
        actor_id=auth.user.id,
        target_id=submission.id,
        details={"status": submission.status.value},
    )
    return _serialize_submission(session, submission)
