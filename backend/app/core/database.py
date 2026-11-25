import os
from dotenv import load_dotenv
from sqlalchemy import URL
from sqlmodel import Session, create_engine
from typing import Annotated
from fastapi import Depends

load_dotenv()

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT")),
    database=os.getenv("MYSQL_DATABASE"),
)

engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]