import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.persistence.base import Base, TimestampMixin

class RunStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        index=True
    )

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status_enum"), 
        default=RunStatus.PENDING, 
        index=True
    )
    
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conversation = relationship("Conversation", backref="runs")