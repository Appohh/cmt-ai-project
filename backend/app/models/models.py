import enum
import uuid
from datetime import datetime
from sqlalchemy import Text, UniqueConstraint, func
from sqlmodel import Field, SQLModel

class Role(enum.Enum):
    author = "author"
    reviewer = "reviewer"
    organizer = "organizer"
    admin = "admin"
    guest = "guest"


class InvitationStatus(enum.Enum):
    invited = "invited"
    accepted = "accepted"
    declined = "declined"


class SubmissionStatus(enum.Enum):
    submitted = "submitted"
    withdrawn = "withdrawn"
    accepted = "accepted"
    rejected = "rejected"


CREATED_AT = {"server_default": func.now()}
UPDATED_AT = {"server_default": func.now(), "onupdate": func.now()}


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True)
    password_hash: str = Field(max_length=255)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    affiliation: str | None = Field(default=None, max_length=255)
    expertise: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)
    role: Role = Field(primary_key=True)
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class Conference(SQLModel, table=True):
    __tablename__ = "conferences"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, sa_type=Text)
    submission_deadline: datetime
    review_deadline: datetime
    notification_deadline: datetime
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conference_id: uuid.UUID = Field(foreign_key="conferences.id")
    email: str = Field(max_length=255)
    role: Role
    status: InvitationStatus = InvitationStatus.invited
    token_hash: str = Field(max_length=255, unique=True)
    expires_at: datetime
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class Submission(SQLModel, table=True):
    __tablename__ = "submissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conference_id: uuid.UUID = Field(foreign_key="conferences.id")
    author_id: uuid.UUID = Field(foreign_key="users.id")
    title: str = Field(max_length=500)
    abstract: str = Field(sa_type=Text)
    file_path: str = Field(max_length=500)
    status: SubmissionStatus = SubmissionStatus.submitted
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class CoAuthor(SQLModel, table=True):
    __tablename__ = "co_authors"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    submission_id: uuid.UUID = Field(foreign_key="submissions.id")
    name: str = Field(max_length=200)
    email: str = Field(max_length=255)
    affiliation: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("submission_id", "reviewer_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    submission_id: uuid.UUID = Field(foreign_key="submissions.id")
    reviewer_id: uuid.UUID = Field(foreign_key="users.id")
    status: InvitationStatus = InvitationStatus.invited
    score: int | None = None
    confidence: int | None = None
    comments: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default=None, sa_column_kwargs=CREATED_AT)
    updated_at: datetime = Field(default=None, sa_column_kwargs=UPDATED_AT)
