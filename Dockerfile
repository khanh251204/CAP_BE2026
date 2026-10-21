# ==============================================================================
# Production Dockerfile for VoiceCashBook Backend
# Hardened, Non-root, Multi-worker, with FFmpeg system dependency
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Install system dependencies (ffmpeg required by AudioPipeline, curl for diagnostics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group for container security
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/sh appuser

WORKDIR /app

# Install Python dependencies first for optimal layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure runtime directories exist with appropriate ownership
RUN mkdir -p /app/logs /app/data_lake && \
    chown -R appuser:appuser /app && \
    chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER appuser

EXPOSE 8000

# Execute pre-flight migrations once before starting multi-worker Uvicorn
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Production CMD: 4 workers, no --reload
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
