from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Import your settings (assuming you have database_url in your config)
from apps.orchestrator.config import settings
from packages.persistence.session import initialize_database, close_database, get_db_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database connection
    initialize_database(settings.database_url)
    yield
    # Shutdown: Cleanly close the database connections
    await close_database()

app = FastAPI(lifespan=lifespan, title="Orchestrator API")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator"}

# Example route demonstrating dependency injection for the DB session
@app.get("/db-ping")
async def db_ping(session: AsyncSession = Depends(get_db_session)):
    """
    Test endpoint to verify database connection injection.
    """
    # Execute a simple query here if needed
    return {"status": "db_connected"}