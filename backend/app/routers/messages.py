from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db, get_or_create_user
from ..models import Message
from ..schemas import MessagesListResponse, MessageResponse, SessionResponse

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/health")
def health():
    return {"status": "ok"}

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


@router.get("/session", response_model=SessionResponse)
def get_session(session_id: str = Query(..., min_length=1, max_length=64), db: Session = Depends(get_db)):
    """Get or create a user session. Called by the frontend on page load."""
    user = get_or_create_user(db, session_id)
    return SessionResponse(
        session_id=user.session_id,
        onboarding_complete=user.onboarding_complete,
        message_count=user.message_count,
    )


@router.get("/messages", response_model=MessagesListResponse)
def get_messages(
    session_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    before_id: Optional[int] = Query(None, description="Load messages with id < before_id (cursor pagination)"),
    db: Session = Depends(get_db),
):
    """
    Paginated message history.

    Access pattern:
    - Initial load (no before_id): returns the most recent `limit` messages in
      chronological order.
    - Infinite-scroll upward (before_id = oldest currently shown message id):
      returns the `limit` messages immediately before that cursor, in
      chronological order.

    Returns has_more=True when there are older messages the client hasn't loaded
    yet, so the frontend knows whether to show a "load more" trigger.
    """
    user = get_or_create_user(db, session_id)

    query = db.query(Message).filter(Message.user_id == user.id)

    if before_id is not None:
        if before_id < 1:
            raise HTTPException(status_code=400, detail="before_id must be a positive integer")
        query = query.filter(Message.id < before_id)

    # Fetch one extra to detect whether more pages exist
    msgs = query.order_by(Message.id.desc()).limit(limit + 1).all()

    has_more = len(msgs) > limit
    if has_more:
        msgs = msgs[:limit]

    msgs.reverse()  # return in chronological order (oldest → newest)

    return MessagesListResponse(
        messages=[MessageResponse.model_validate(m) for m in msgs],
        has_more=has_more,
    )
