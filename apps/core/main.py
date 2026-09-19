from fastapi import FastAPI
from apps.core.config import settings

app = FastAPI(title="Core API")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "core"}
