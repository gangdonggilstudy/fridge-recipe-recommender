from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DB_URL

engine = create_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)