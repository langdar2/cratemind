# Stage 1: build wheels that require C compilation (implicit, scipy, numpy)
FROM python:3.14.3-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libopenblas-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: lean runtime image
FROM python:3.14.3-slim

ARG VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${VERSION}

WORKDIR /app

# Copy pre-built packages from builder
COPY --from=builder /install /usr/local

# Create a non-root user with specific UID for easier host permission matching
RUN groupadd -r -g 1000 cratemindappuser && useradd -r -u 1000 -g cratemindappuser cratemindappuser

# Create data directory with correct ownership (for volume mounts)
RUN mkdir -p /app/data && chown cratemindappuser:cratemindappuser /app/data

# Copy application code with ownership
COPY --chown=cratemindappuser:cratemindappuser backend/ ./backend/
COPY --chown=cratemindappuser:cratemindappuser frontend/ ./frontend/

# Expose port
EXPOSE 5765

# Switch to non-root user
USER cratemindappuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; import sys; code = urllib.request.urlopen('http://localhost:5765/api/health').getcode(); sys.exit(0 if code == 200 else 1)"

# Run the application
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 5765 --workers ${UVICORN_WORKERS:-1}"]
