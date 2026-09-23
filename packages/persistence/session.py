from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = None
async_session_factory = None

def initialize_database(database_url: str) -> None:
    global engine, async_session_factory
    
    engine = create_async_engine(database_url, echo=False, future=True)
    async_session_factory = async_sessionmaker(
        bind=engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

async def close_database() -> None:
    global engine
    if engine is not None:
        await engine.dispose()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Database is not initialized.")
    
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
        finally:
            await session.close()
