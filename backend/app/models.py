from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    long_term_memory = Column(JSON, default=dict)       # extracted user facts
    conversation_summary = Column(Text, nullable=True)  # summary of older messages
    onboarding_complete = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)          # total messages exchanged
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    role = Column(String(16), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    category = Column(String(64), nullable=False)
    keywords = Column(JSON, nullable=False)  # list of trigger keywords
    content = Column(Text, nullable=False)
    priority = Column(Integer, default=0)    # higher = shown first when tied
