FROM python:3.12-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy pyproject.toml
COPY pyproject.toml .

# Extract dependencies using Python 3.12 built-in tomllib and install them
RUN python -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; print('\n'.join(deps))" > requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code and Alembic files
COPY apps/orchestrator apps/orchestrator
COPY packages packages
COPY alembic alembic
COPY alembic.ini .

# Set permissions
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

CMD ["sh", "-c", "alembic upgrade head && uvicorn apps.orchestrator.main:app --host 0.0.0.0 --port 8001"]
