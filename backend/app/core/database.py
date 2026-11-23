import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

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