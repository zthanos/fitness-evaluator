FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml pyproject.lock* ./
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY app/ ./app/
COPY public/ ./public/
COPY .env* ./

# Install Python dependencies
RUN pip install --upgrade pip uv && \
    uv sync --frozen --no-dev

# Create database directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations and start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
