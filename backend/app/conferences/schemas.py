import uuid
from datetime import datetime
from sqlmodel import SQLModel


class ConferencePublic(SQLModel):
    id: uuid.UUID
    name: str
    description: str | None
    submission_deadline: datetime
    review_deadline: datetime
    notification_deadline: datetime
