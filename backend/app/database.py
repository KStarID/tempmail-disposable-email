"""
Database session and helpers.
"""

import os
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/tempmail.db")

# SQLite: enable WAL mode for better concurrent reads
connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode and foreign keys for SQLite"""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def init_db():
    """Create all tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency for FastAPI"""
    with Session(engine) as session:
        yield session
