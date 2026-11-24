from fastapi import APIRouter
from sqlmodel import select
from app.conferences.schemas import ConferencePublic
from app.core.database import SessionDep
from app.models.models import Conference

router = APIRouter(prefix="/conferences", tags=["conferences"])


@router.get("/", response_model=list[ConferencePublic])
def list_conferences(session: SessionDep):
    return session.exec(select(Conference)).all()
