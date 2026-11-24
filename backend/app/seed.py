# Local test data only, never run this in production.
# Run once on an empty database: python -m app.seed
import hashlib
from datetime import datetime, timezone
from pwdlib import PasswordHash
from sqlmodel import Session
from app.core.database import engine
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

password_hash = PasswordHash.recommended()

with Session(engine) as session:
    # One user per role
    users = {
        role: User(
            email=f"{role.value}@example.com",
            password_hash=password_hash.hash("password"),
            first_name=role.value.capitalize(),
            last_name="Test",
            affiliation="Example University",
            expertise="Deep learning",
        )
        for role in Role
    }
    conference = Conference(
        name="EAMT 2028",
        description="Example conference",
        submission_deadline=datetime(2028, 3, 1, tzinfo=timezone.utc),
        review_deadline=datetime(2028, 4, 15, tzinfo=timezone.utc),
        notification_deadline=datetime(2028, 5, 1, tzinfo=timezone.utc),
    )
    session.add_all([*users.values(), conference])
    session.flush()

    # Everyone is an author, plus their own role
    for role, user in users.items():
        for user_role in {Role.author, role}:
            session.add(UserRole(user_id=user.id, role=user_role))

    # One invitation per status
    for status, email, role in [
        (InvitationStatus.invited, "invited@example.com", Role.guest),
        (InvitationStatus.accepted, "reviewer@example.com", Role.reviewer),
        (InvitationStatus.declined, "declined@example.com", Role.reviewer),
    ]:
        session.add(Invitation(
            conference_id=conference.id,
            email=email,
            role=role,
            status=status,
            token_hash=hashlib.sha256(email.encode()).hexdigest(),
            expires_at=datetime(2028, 1, 1, tzinfo=timezone.utc),
        ))

    # One submission per status
    submissions = {
        status: Submission(
            conference_id=conference.id,
            author_id=users[Role.author].id,
            title=f"Example paper ({status.value})",
            abstract="Example abstract about deep learning.",
            file_path=f"example-{status.value}.pdf",
            status=status,
        )
        for status in SubmissionStatus
    }
    session.add_all(submissions.values())
    session.flush()

    session.add(CoAuthor(
        submission_id=submissions[SubmissionStatus.submitted].id,
        name="Co Author",
        email="coauthor@example.com",
        affiliation="Example University",
    ))

    # One review per status
    reviewer_id = users[Role.reviewer].id
    session.add_all([
        Review(
            submission_id=submissions[SubmissionStatus.submitted].id,
            reviewer_id=reviewer_id,
            status=InvitationStatus.invited,
        ),
        Review(
            submission_id=submissions[SubmissionStatus.accepted].id,
            reviewer_id=reviewer_id,
            status=InvitationStatus.accepted,
            score=4,
            confidence=5,
            comments="Good method, clear evaluation.",
        ),
        Review(
            submission_id=submissions[SubmissionStatus.rejected].id,
            reviewer_id=reviewer_id,
            status=InvitationStatus.declined,
        ),
    ])
    session.commit()

print("Seeded")
