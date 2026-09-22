import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from packages.persistence.models.run import Run, RunStatus
from packages.persistence.models.audit import AuditEvent

class TrackingService:
    @staticmethod
    async def create_run(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Run:
        """Create a new run record for the incoming request."""
        new_run = Run(
            conversation_id=conversation_id,
            status=RunStatus.PENDING,
            provider=provider,
            model_name=model_name
        )
        session.add(new_run)
        await session.flush() # Flush to get the ID without committing
        return new_run

    @staticmethod
    async def update_run(
        session: AsyncSession,
        run_id: uuid.UUID,
        status: RunStatus,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update the existing run with final status and token usage."""
        total_tokens = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status=status,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                error_message=error_message
            )
        )
        await session.flush()

    @staticmethod
    async def log_audit(
        session: AsyncSession,
        request_id: str,
        event_type: str,
        action: str,
        run_id: Optional[uuid.UUID] = None,
        payload: Optional[dict[str, Any]] = None
    ) -> None:
        """Log safety or policy decisions in the audit table."""
        event = AuditEvent(
            request_id=request_id,
            event_type=event_type,
            action=action,
            run_id=run_id,
            payload=payload
        )
        session.add(event)
        await session.flush()