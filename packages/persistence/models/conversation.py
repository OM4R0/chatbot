import uuid
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.persistence.base import Base, TimestampMixin

class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    # Internal identifier
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Optional external identifier (e.g., from Open WebUI)
    external_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)

    # Relationship to messages
    messages: Mapped[List["Message"]] = relationship(
        "Message", 
        back_populates="conversation", 
        cascade="all, delete-orphan",
        order_by="Message.sequence_number" # Keeps messages ordered
    )

class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        index=True
    )
    
    # 'user' or 'assistant'
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    # To maintain the order of messages in the conversation
    sequence_number: Mapped[int] = mapped_column(Integer)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", 
        back_populates="messages"
    )