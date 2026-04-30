# ── Stage 1: Install Python dependencies ───────────────────────────────────
# Using slim variant (no dev tools) keeps the final image small (~400MB vs ~1GB)
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for some packages (numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install to a local prefix so we can copy just the deps in the next stage
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime image ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY api/    ./api/
COPY ml/     ./ml/
COPY db/     ./db/

# These dirs are volume-mounted from the host at runtime
RUN mkdir -p /app/data /app/models

# Set Python path so `from api.xxx import` and `from ml.xxx import` work
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# uvicorn: the ASGI server that runs FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
