# Dockerfile for Fitness Evaluator FastAPI application
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Copy application code
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY app/ ./app/
COPY public/ ./public/

# Install Python dependencies
RUN pip install --upgrade pip uv && \
    uv sync --frozen --no-dev

# Create database and cache directories and set ownership
RUN mkdir -p /app/data \
    && mkdir -p /home/appuser/.cache/uv \
    && mkdir -p /tmp/uv-cache \
    && chown -R appuser:appuser /app /home/appuser /tmp/uv-cache

# Configure uv cache directory to a writable path
ENV UV_CACHE_DIR=/tmp/uv-cache

# Switch to non-root user
USER appuser

# Health check - allows 30s for migrations to complete
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations separately before starting:
# docker-compose run app uv run alembic upgrade head
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]