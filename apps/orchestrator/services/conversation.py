import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from packages.persistence.models.conversation import Conversation, Message
from packages.providers.schemas import Message as ProviderMessage

class ConversationService:
    
    @staticmethod
    async def get_or_create_conversation(
        session: AsyncSession, 
        external_id: Optional[str] = None
    ) -> Conversation:
        """Find existing conversation by external_id or create a new one."""
        if external_id:
            result = await session.execute(
                select(Conversation).where(Conversation.external_id == external_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                return conversation

        # Create new conversation if not found or no external_id provided
        new_conversation = Conversation(external_id=external_id)
        session.add(new_conversation)
        await session.flush() # Flush to get the generated UUID without committing yet
        return new_conversation

    @staticmethod
    async def add_messages_to_conversation(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        messages: List[ProviderMessage]
    ) -> None:
        """Append new messages to a conversation transactionally."""
        # Get the current maximum sequence number to keep messages ordered
        result = await session.execute(
            select(Message.sequence_number)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_number.desc())
            .limit(1)
        )
        last_seq = result.scalar_one_or_none() or 0

        # Add new messages
        for idx, msg in enumerate(messages, start=1):
            new_message = Message(
                conversation_id=conversation_id,
                role=msg.role,
                content=msg.content,
                sequence_number=last_seq + idx
            )
            session.add(new_message)
            
        # The request-scoped database dependency commits after the workflow also
        # updates its run record. This keeps the conversation and run atomic.
        await session.flush()
