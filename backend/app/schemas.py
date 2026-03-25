from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool


class SessionResponse(BaseModel):
    session_id: str
    onboarding_complete: bool
    message_count: int
