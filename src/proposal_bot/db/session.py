from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from proposal_bot.db.models import Base

# Ensure local data directory exists right in your project folder
Path("proposal_db").mkdir(exist_ok=True)

# Pure local SQLite database file — no external server required
db_url = "sqlite:///proposal_db/records.db"
engine = create_engine(db_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Creates the SQLite database tables on startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database sessions."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()