"""FastAPI application entrypoint wiring all C4 domain routers and CORS."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.conferences.router import invitations_router, router as conferences_router
from app.core.database import engine, init_db, is_sqlite_engine
from app.reviews.router import router as reviews_router
from app.submissions.router import router as submissions_router
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if is_sqlite_engine():
        init_db()
    yield


app = FastAPI(title="EAMT CMT API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conferences_router)
app.include_router(invitations_router)
app.include_router(submissions_router)
app.include_router(reviews_router)
app.include_router(ai_router)


@app.get("/")
def read_root():
    return {"message": "EAMT CMT FastAPI backend is running."}


@app.get("/db-test")
def db_test():
    with engine.connect():
        return {"database": "connected"}
