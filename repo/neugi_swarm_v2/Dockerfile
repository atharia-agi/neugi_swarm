FROM python:3.12-slim AS base

LABEL maintainer="NEUGI Team <contact@neugi.ai>"
LABEL description="NEUGI Swarm V2 - Distributed AI Agent Orchestration Platform"
LABEL version="2.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NEUGI_ENV=production

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN groupadd -r neugi && useradd -r -g neugi -d /app -s /sbin/nologin neugi && \
    chown -R neugi:neugi /app

USER neugi

# Expose ports
EXPOSE 19887 19888 19889 19890

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:19887/health || exit 1

# Entrypoint
ENTRYPOINT ["neugi", "start"]
