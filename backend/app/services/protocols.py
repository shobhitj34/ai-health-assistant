from sqlalchemy.orm import Session
from ..models import Protocol

MAX_PROTOCOLS = 3  # max protocols to inject into context


def match_protocols(message: str, db: Session) -> list[Protocol]:
    """
    Return up to MAX_PROTOCOLS protocols whose keywords appear in the message.
    Sorted by priority descending, then by number of keyword hits descending.
    """
    if not message or not message.strip():
        return []

    message_lower = message.lower()
    scored: list[tuple[int, int, Protocol]] = []  # (hits, priority, protocol)

    protocols = db.query(Protocol).all()
    for p in protocols:
        hits = sum(1 for kw in p.keywords if kw.lower() in message_lower)
        if hits > 0:
            scored.append((hits, p.priority, p))

    # Sort: most hits first, then highest priority
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [p for _, _, p in scored[:MAX_PROTOCOLS]]
