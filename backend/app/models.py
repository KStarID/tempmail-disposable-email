"""
Database models for Disposable Email Service.
Uses SQLModel (SQLAlchemy + Pydantic combined).
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, Index
from sqlalchemy.types import Integer, String, Text, Boolean, DateTime


def utcnow():
    return datetime.now(timezone.utc)


class Inbox(SQLModel, table=True):
    """One disposable email address."""
    __tablename__ = "inboxes"

    id: Optional[int] = Field(default=None, primary_key=True)
    address: str = Field(sa_column=Column(String(255), unique=True, index=True, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False, index=True)
    ip_address: Optional[str] = Field(default=None, sa_column=Column(String(64)))
    deleted: bool = Field(default=False, nullable=False)

    messages: List["Message"] = Relationship(
        back_populates="inbox",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Message(SQLModel, table=True):
    """One received email."""
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    inbox_id: int = Field(foreign_key="inboxes.id", nullable=False, index=True)
    from_address: str = Field(default="", sa_column=Column(String(512)))
    from_name: Optional[str] = Field(default=None, sa_column=Column(String(255)))
    subject: str = Field(default="", sa_column=Column(Text))
    body_text: str = Field(default="", sa_column=Column(Text))
    body_html: str = Field(default="", sa_column=Column(Text))
    received_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
    read: bool = Field(default=False, nullable=False)
    size_bytes: int = Field(default=0, nullable=False)

    inbox: Optional[Inbox] = Relationship(back_populates="messages")


# ---- DTOs (request/response models) ----

class CreateInboxResponse(SQLModel):
    id: int
    address: str
    created_at: datetime
    expires_at: datetime


class MessageSummary(SQLModel):
    id: int
    from_address: str
    from_name: Optional[str]
    subject: str
    received_at: datetime
    read: bool


class MessageDetail(SQLModel):
    id: int
    inbox_id: int
    from_address: str
    from_name: Optional[str]
    subject: str
    body_text: str
    body_html: str
    received_at: datetime
    read: bool


class IncomingEmailPayload(SQLModel):
    """Payload from Postfix catcher script"""
    recipient: str
    from_: str = Field(alias="from")
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    raw_size: int = 0
    received_at: str

    class Config:
        populate_by_name = True
