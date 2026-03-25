from typing import Optional
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./disha.db")

# connect_args only needed for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    from .models import Base
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── helper functions (thin wrappers so services stay import-clean) ──────────

def get_or_create_user(db: Session, session_id: str):
    from .models import User
    user = db.query(User).filter(User.session_id == session_id).first()
    if not user:
        user = User(session_id=session_id, long_term_memory={})
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def save_message(db: Session, user_id: int, role: str, content: str):
    from .models import Message
    msg = Message(user_id=user_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def update_user_count(db: Session, user_id: int, new_count: int):
    from .models import User
    db.query(User).filter(User.id == user_id).update(
        {"message_count": new_count, "updated_at": datetime.utcnow()}
    )
    db.commit()


def update_user_memory(
    db: Session,
    user_id: int,
    memory: dict,
    onboarding_complete: bool,
    summary: Optional[str] = None,
):
    from .models import User
    update = {
        "long_term_memory": memory,
        "onboarding_complete": onboarding_complete,
        "updated_at": datetime.utcnow(),
    }
    if summary is not None:
        update["conversation_summary"] = summary
    db.query(User).filter(User.id == user_id).update(update)
    db.commit()
