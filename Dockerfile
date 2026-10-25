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

# Install runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for Hugging Face compliance
RUN useradd -m -u 1000 user
USER user

# Copy the installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy our application code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# Hugging Face routes traffic to port 7860 by default
EXPOSE 7860

# Start the server, binding to the required port
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 7860"]