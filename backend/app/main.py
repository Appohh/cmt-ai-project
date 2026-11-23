from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
)

@app.get("/")
def read_root():
    return {"message": "This is a message from the FastAPI backend."}