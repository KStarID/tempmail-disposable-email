"""
Business logic: inbox creation, message storage, expiry.
"""

import os
import secrets
import string
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select
from fastapi import HTTPException

from .models import Inbox, Message, utcnow

DOMAIN = os.environ.get("DOMAIN", "kstarid.cloud")
INBOX_TTL_MINUTES = int(os.environ.get("INBOX_TTL_MINUTES", "60"))

LOCAL_PART_ALPHABET = string.ascii_lowercase + string.digits


def generate_local_part(length: int = 12) -> str:
    """Cryptographically random local-part like 'a3kx9p2m4nq8'"""
    return "".join(secrets.choice(LOCAL_PART_ALPHABET) for _ in range(length))


def parse_recipient(raw: str) -> Optional[str]:
    """Extract local-part from 'random@kstarid.cloud'"""
    if not raw:
        return None
    m = re.match(r"^([^@]+)@([^@]+)$", raw.strip().lower())
    if not m:
        return None
    local, domain = m.group(1), m.group(2)
    if domain != DOMAIN:
        return None
    if not re.match(r"^[a-z0-9._-]+$", local):
        return None
    return raw.strip().lower()


def get_or_create_inbox(
    session: Session,
    recipient: str,
    ip_address: Optional[str] = None,
) -> Inbox:
    """
    Get existing inbox OR create a new one.
    If existing, refresh expiry.
    """
    parsed = parse_recipient(recipient)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"invalid recipient address: {recipient}")

    now = utcnow()
    expires_at = now + timedelta(minutes=INBOX_TTL_MINUTES)

    stmt = select(Inbox).where(Inbox.address == parsed, Inbox.deleted == False)
    existing = session.exec(stmt).first()

    if existing:
        # Refresh expiry
        existing.expires_at = expires_at
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    inbox = Inbox(
        address=parsed,
        created_at=now,
        expires_at=expires_at,
        ip_address=ip_address,
    )
    session.add(inbox)
    session.commit()
    session.refresh(inbox)
    return inbox


def store_message(
    session: Session,
    recipient: str,
    from_address: str,
    subject: str,
    body_text: str,
    body_html: str,
    raw_size: int = 0,
) -> tuple[Inbox, Message]:
    """Store an incoming email message in the recipient's inbox"""
    inbox = get_or_create_inbox(session, recipient)

    msg = Message(
        inbox_id=inbox.id,
        from_address=from_address,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        received_at=utcnow(),
        read=False,
        size_bytes=raw_size,
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return inbox, msg


def expire_old_inboxes(session: Session) -> int:
    """Soft-delete expired inboxes. Returns count deleted."""
    now = utcnow()
    stmt = select(Inbox).where(Inbox.expires_at < now, Inbox.deleted == False)
    inboxes = session.exec(stmt).all()
    for inbox in inboxes:
        inbox.deleted = True
        session.add(inbox)
    session.commit()
    return len(inboxes)
