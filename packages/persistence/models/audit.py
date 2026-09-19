import uuid
from typing import Optional, Any
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.persistence.base import Base, TimestampMixin

class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Optional link to a specific run
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Correlation and tracing identifiers
    request_id: Mapped[str] = mapped_column(String(255), index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    # Event category and action (e.g., "input_guardrail", "policy_rejection", "route_selection")
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(100))

    # Structured metadata containing decisions (ensuring no secrets or credentials are stored)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    run = relationship("Run", backref="audit_events")