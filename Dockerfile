# ---- Stage 1: Builder ----
FROM python:3.11.9-slim AS builder
WORKDIR /app

# Install build tools needed for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install dependencies into a specific folder
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: Runtime ----
FROM python:3.11.9-slim
WORKDIR /app

# Install ONLY the runtime libraries needed (libgomp1 for FastEmbed, libpq5 for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

EXPOSE 8000

# Run migrations, then start the server (Free tier compatible)
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]