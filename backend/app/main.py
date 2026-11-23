from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
)

@app.get("/")
def read_root():
    return {"message": "This is a message from the FastAPI backend."}

@app.get("/db-test")
def db_test():
    with engine.connect():
        return {"database": "connected"}