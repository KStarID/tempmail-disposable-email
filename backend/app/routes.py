"""
FastAPI routes for Disposable Email Service.
"""

import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .database import get_session, init_db
from .models import (
    Inbox,
    Message,
    CreateInboxResponse,
    MessageSummary,
    MessageDetail,
    IncomingEmailPayload,
    utcnow,
)
from .services import (
    DOMAIN,
    INBOX_TTL_MINUTES,
    generate_local_part,
    parse_recipient,
    get_or_create_inbox,
    store_message,
    expire_old_inboxes,
)


router = APIRouter()


# ============================================================
# Public API
# ============================================================

@router.post("/api/inbox/create", response_model=CreateInboxResponse)
def create_inbox_endpoint(request: Request, session: Session = Depends(get_session)):
    """Create a new random inbox."""
    client_ip = request.client.host if request.client else None

    local = generate_local_part()
    address = f"{local}@{DOMAIN}"

    inbox = get_or_create_inbox(session, address, ip_address=client_ip)
    return CreateInboxResponse(
        id=inbox.id,
        address=inbox.address,
        created_at=inbox.created_at,
        expires_at=inbox.expires_at,
    )


@router.get("/api/inbox/{address}", response_model=CreateInboxResponse)
def get_inbox_endpoint(address: str, session: Session = Depends(get_session)):
    """Get inbox details (extending expiry if still valid)."""
    parsed = parse_recipient(address)
    if not parsed:
        raise HTTPException(status_code=400, detail="invalid address")

    inbox = get_or_create_inbox(session, parsed)
    return CreateInboxResponse(
        id=inbox.id,
        address=inbox.address,
        created_at=inbox.created_at,
        expires_at=inbox.expires_at,
    )


@router.get("/api/inbox/{address}/messages", response_model=List[MessageSummary])
def list_messages_endpoint(address: str, session: Session = Depends(get_session)):
    """List all messages in an inbox."""
    parsed = parse_recipient(address)
    if not parsed:
        raise HTTPException(status_code=400, detail="invalid address")

    stmt = (
        select(Message)
        .join(Inbox, Inbox.id == Message.inbox_id)
        .where(Inbox.address == parsed, Inbox.deleted == False, Inbox.expires_at > utcnow())
        .order_by(Message.received_at.desc())
    )
    messages = session.exec(stmt).all()

    return [
        MessageSummary(
            id=m.id,
            from_address=m.from_address,
            from_name=m.from_name,
            subject=m.subject,
            received_at=m.received_at,
            read=m.read,
        )
        for m in messages
    ]


@router.get("/api/inbox/{address}/messages/{msg_id}", response_model=MessageDetail)
def get_message_endpoint(address: str, msg_id: int, session: Session = Depends(get_session)):
    """Get full message content (also marks as read)."""
    parsed = parse_recipient(address)
    if not parsed:
        raise HTTPException(status_code=400, detail="invalid address")

    stmt = (
        select(Message)
        .join(Inbox, Inbox.id == Message.inbox_id)
        .where(
            Inbox.address == parsed,
            Inbox.deleted == False,
            Inbox.expires_at > utcnow(),
            Message.id == msg_id,
        )
    )
    msg = session.exec(stmt).first()
    if not msg:
        raise HTTPException(status_code=404, detail="message not found")

    if not msg.read:
        msg.read = True
        session.add(msg)
        session.commit()
        session.refresh(msg)

    return MessageDetail(
        id=msg.id,
        inbox_id=msg.inbox_id,
        from_address=msg.from_address,
        from_name=msg.from_name,
        subject=msg.subject,
        body_text=msg.body_text,
        body_html=msg.body_html,
        received_at=msg.received_at,
        read=msg.read,
    )


@router.delete("/api/inbox/{address}")
def delete_inbox_endpoint(address: str, session: Session = Depends(get_session)):
    """Manually expire an inbox."""
    parsed = parse_recipient(address)
    if not parsed:
        raise HTTPException(status_code=400, detail="invalid address")

    stmt = select(Inbox).where(Inbox.address == parsed)
    inbox = session.exec(stmt).first()
    if not inbox:
        raise HTTPException(status_code=404, detail="inbox not found")

    inbox.deleted = True
    session.add(inbox)
    session.commit()
    return {"ok": True, "address": parsed}


# ============================================================
# Internal API (called by Postfix catcher script)
# ============================================================

@router.post("/api/internal/incoming")
def incoming_email_endpoint(
    payload: IncomingEmailPayload,
    session: Session = Depends(get_session),
):
    """Receive a parsed email from Postfix catcher script."""
    try:
        received_at_dt = datetime.fromisoformat(payload.received_at)
    except Exception:
        received_at_dt = utcnow()

    inbox, msg = store_message(
        session=session,
        recipient=payload.recipient,
        from_address=payload.from_,
        subject=payload.subject,
        body_text=payload.body_text,
        body_html=payload.body_html,
        raw_size=payload.raw_size,
    )
    msg.received_at = received_at_dt
    session.add(msg)
    session.commit()
    session.refresh(msg)

    return {
        "ok": True,
        "inbox_id": inbox.id,
        "message_id": msg.id,
        "address": inbox.address,
    }


# ============================================================
# Maintenance
# ============================================================

@router.post("/api/internal/cleanup")
def cleanup_endpoint(session: Session = Depends(get_session)):
    """Soft-delete expired inboxes."""
    count = expire_old_inboxes(session)
    return {"ok": True, "deleted_count": count}


@router.get("/api/health")
def health_endpoint():
    return {"status": "ok", "service": "tempmail-backend", "domain": DOMAIN, "ttl_minutes": INBOX_TTL_MINUTES}
