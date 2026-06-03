# # from sqlalchemy import create_engine
# # from sqlalchemy.orm import sessionmaker

# # from config import DB_URL

# # engine = create_engine(
# #     DB_URL,
# #     echo=False,
# #     pool_pre_ping=True,
# #     pool_recycle=3600
# # )

# # SessionLocal = sessionmaker(
# #     autocommit=False,
# #     autoflush=False,
# #     bind=engine
# # )

# import os
# from pathlib import Path

# from dotenv import load_dotenv
# from sqlalchemy import create_engine, event


# BASE_DIR = Path(__file__).resolve().parent.parent
# DATA_DIR = BASE_DIR / "data"
# DATA_DIR.mkdir(parents=True, exist_ok=True)

# load_dotenv(BASE_DIR / ".env")

# DEFAULT_DB_URL = f"sqlite:///{DATA_DIR / 'recipe_project.db'}"
# DB_URL = os.getenv("DB_URL", DEFAULT_DB_URL)

# connect_args = {}

# if DB_URL.startswith("sqlite"):
#     connect_args = {
#         "check_same_thread": False
#     }

# engine = create_engine(
#     DB_URL,
#     future=True,
#     connect_args=connect_args
# )


# @event.listens_for(engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     if not DB_URL.startswith("sqlite"):
#         return

#     cursor = dbapi_connection.cursor()
#     cursor.execute("PRAGMA foreign_keys = ON")
#     cursor.execute("PRAGMA journal_mode = WAL")
#     cursor.close()


import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env", override=True)

DEFAULT_DB_URL = f"sqlite:///{DATA_DIR / 'recipe_project.db'}"
DB_URL = os.getenv("DB_URL") or DEFAULT_DB_URL

connect_args = {}

if DB_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }

engine = create_engine(
    DB_URL,
    future=True,
    connect_args=connect_args
)

DB_DIALECT = engine.dialect.name
# sqlite / mysql 등으로 나옴


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DB_DIALECT != "sqlite":
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()
