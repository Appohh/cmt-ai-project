"""ReviewComponent HTTP endpoints: assignments, accept/decline, double-blind views & scoring."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.core.config import ensure_utc, utcnow
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
    User,
)
from app.reviews import service as reviews_service
from app.reviews.schemas import (
    AssignReviewerRequest,
    BlindSubmissionPublic,
    ReviewAssignmentPublic,
    ReviewRespondRequest,
    ReviewSubmitRequest,
)
from app.submissions.pre_check import strip_pdf_metadata
from app.submissions.service import anonymize_submission_for_reviewer

router = APIRouter(tags=["reviews"])


def _serialize_assignment(
    session: Session,
    review: Review,
    submission: Submission | None = None,
    conference: Conference | None = None,
) -> ReviewAssignmentPublic:
    sub = submission or session.get(Submission, review.submission_id)
    conf = conference or (session.get(Conference, sub.conference_id) if sub else None)
    if sub is None or conf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    anonymized = anonymize_submission_for_reviewer(
        {
            "id": sub.id,
            "conference_id": sub.conference_id,
            "author_id": sub.author_id,
            "title": sub.title,
            "abstract": sub.abstract,
        }
    )
    can_review = (
        review.status == InvitationStatus.accepted
        and utcnow() <= ensure_utc(conf.review_deadline)
    )
    return ReviewAssignmentPublic(
        id=review.id,
        submission_id=sub.id,
        conference_id=conf.id,
        conference_name=conf.name,
        title=anonymized["title"],
        abstract=anonymized["abstract"],
        review_deadline=conf.review_deadline,
        status=review.status.value,
        score=review.score,
        confidence=review.confidence,
        comments=review.comments,
        can_review=can_review,
    )


def _get_assigned_review_or_403(
    session: Session, submission_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Review, Submission]:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    review = session.exec(
        select(Review).where(
            Review.submission_id == submission_id,
            Review.reviewer_id == user_id,
            Review.status != InvitationStatus.declined,
        )
    ).first()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an assigned reviewer for this submission",
        )
    return review, submission


@router.post("/submissions/{submission_id}/assign", status_code=status.HTTP_201_CREATED)
def assign_reviewer_endpoint(
    submission_id: uuid.UUID,
    payload: AssignReviewerRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Assign a reviewer to a submission after enforcing conflict-of-interest checks."""
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    reviewer = session.get(User, payload.reviewer_id)
    if reviewer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    co_authors = session.exec(
        select(CoAuthor).where(CoAuthor.submission_id == submission.id)
    ).all()

    try:
        reviews_service.assign_reviewer(
            submission={
                "id": submission.id,
                "author_id": submission.author_id,
                "co_authors": [{"email": ca.email} for ca in co_authors],
            },
            reviewer_id=reviewer.id,
            reviewer_email=reviewer.email,
        )
    except reviews_service.ConflictOfInterestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing = session.exec(
        select(Review).where(
            Review.submission_id == submission.id,
            Review.reviewer_id == reviewer.id,
        )
    ).first()
    if existing is not None:
        if existing.status == InvitationStatus.declined:
            existing.status = InvitationStatus.invited
            session.add(existing)
            session.commit()
            session.refresh(existing)
            log_action(
                "review.reassigned",
                actor_id=auth.user.id,
                target_id=existing.id,
                details={"submission_id": str(submission.id), "reviewer_id": str(reviewer.id)},
            )
            return {
                "id": str(existing.id),
                "submission_id": str(submission.id),
                "reviewer_id": str(reviewer.id),
                "status": existing.status.value,
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer is already assigned to this submission",
        )

    review = Review(
        submission_id=submission.id,
        reviewer_id=reviewer.id,
        status=InvitationStatus.invited,
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    log_action(
        "review.assigned",
        actor_id=auth.user.id,
        target_id=review.id,
        details={"submission_id": str(submission.id), "reviewer_id": str(reviewer.id)},
    )
    return {
        "id": str(review.id),
        "submission_id": str(submission.id),
        "reviewer_id": str(reviewer.id),
        "status": review.status.value,
    }


@router.delete("/submissions/{submission_id}/assign/{reviewer_id}")
def unassign_reviewer_endpoint(
    submission_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.organizer)),
):
    """Remove an uncompleted reviewer assignment from a submission."""
    review = session.exec(
        select(Review).where(
            Review.submission_id == submission_id,
            Review.reviewer_id == reviewer_id,
        )
    ).first()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if review.score is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unassign a reviewer who has already submitted a score",
        )

    session.delete(review)
    session.commit()
    log_action(
        "review.unassigned",
        actor_id=auth.user.id,
        target_id=submission_id,
        details={"reviewer_id": str(reviewer_id)},
    )
    return {"status": "unassigned"}


@router.get("/reviews/assigned", response_model=list[ReviewAssignmentPublic])
def list_assigned_reviews(
    session: SessionDep,
    conference_id: uuid.UUID | None = None,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Return double-blind review assignments for the authenticated reviewer."""
    reviews = session.exec(
        select(Review).where(Review.reviewer_id == auth.user.id).order_by(Review.created_at.desc())
    ).all()

    results: list[ReviewAssignmentPublic] = []
    for review in reviews:
        sub = session.get(Submission, review.submission_id)
        if sub is None:
            continue
        if conference_id is not None and sub.conference_id != conference_id:
            continue
        conf = session.get(Conference, sub.conference_id)
        if conf is None:
            continue
        results.append(_serialize_assignment(session, review, sub, conf))
    return results


@router.post("/reviews/{review_id}/respond", response_model=ReviewAssignmentPublic)
def respond_to_review_invitation(
    review_id: uuid.UUID,
    payload: ReviewRespondRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Accept or decline a paper review invitation."""
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.reviewer_id != auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to respond to this review invitation",
        )

    review.status = InvitationStatus(payload.status)
    session.add(review)
    session.commit()
    session.refresh(review)

    log_action(
        "review.responded",
        actor_id=auth.user.id,
        target_id=review.id,
        details={"status": review.status.value},
    )
    return _serialize_assignment(session, review)


@router.put("/reviews/{review_id}", response_model=ReviewAssignmentPublic)
def submit_or_update_review(
    review_id: uuid.UUID,
    payload: ReviewSubmitRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Submit or edit score, confidence, and written feedback before review_deadline."""
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.reviewer_id != auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this review",
        )
    if review.status != InvitationStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review invitation must be accepted before submitting feedback",
        )

    submission = session.get(Submission, review.submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    conference = session.get(Conference, submission.conference_id)
    if conference is None or utcnow() > ensure_utc(conference.review_deadline):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review deadline has passed for this conference",
        )

    clean_comments = payload.comments.strip()
    if not clean_comments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Written review comments are required",
        )

    review.score = payload.score
    review.confidence = payload.confidence
    review.comments = clean_comments
    session.add(review)
    session.commit()
    session.refresh(review)

    log_action(
        "review.submitted",
        actor_id=auth.user.id,
        target_id=review.id,
        details={"score": review.score, "confidence": review.confidence},
    )
    return _serialize_assignment(session, review, submission, conference)


@router.get("/reviews/submissions/{submission_id}", response_model=BlindSubmissionPublic)
def get_blind_submission_for_reviewer(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Return strictly anonymized submission metadata to an assigned reviewer (IDOR-protected)."""
    review, submission = _get_assigned_review_or_403(session, submission_id, auth.user.id)
    anonymized = anonymize_submission_for_reviewer(
        {
            "id": submission.id,
            "conference_id": submission.conference_id,
            "author_id": submission.author_id,
            "title": submission.title,
            "abstract": submission.abstract,
            "status": submission.status.value,
        }
    )
    return BlindSubmissionPublic(
        id=anonymized["id"],
        conference_id=anonymized["conference_id"],
        title=anonymized["title"],
        abstract=anonymized["abstract"],
        status=anonymized["status"],
        review_id=review.id,
        review_status=review.status.value,
        score=review.score,
        confidence=review.confidence,
        comments=review.comments,
    )


@router.get("/reviews/submissions/{submission_id}/pdf")
def download_blind_pdf_for_reviewer(
    submission_id: uuid.UUID,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Serve a metadata-stripped PDF exclusively to assigned reviewers (IDOR-protected)."""
    _review, submission = _get_assigned_review_or_403(session, submission_id, auth.user.id)
    pdf_path = Path(submission.file_path)
    if not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    clean_pdf = strip_pdf_metadata(pdf_path.read_bytes())
    log_action(
        "review.blind_pdf_downloaded",
        actor_id=auth.user.id,
        target_id=submission.id,
    )
    return Response(
        content=clean_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="blind-paper-{submission_id}.pdf"'},
    )
