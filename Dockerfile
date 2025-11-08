# Revival Scanner - Production Dockerfile for Railway Deployment
# Moon Dev AI Agents - Meme Coin Trading Bot

FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements-production.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-production.txt

# Copy application code
COPY src/ ./src/
COPY start_webapp.sh .

# Create data directory for persistent storage
RUN mkdir -p /app/src/data/paper_trading \
    /app/src/data/meme_scanner \
    /app/src/data/security_filter \
    /app/src/data/ohlcv

# Make start script executable
RUN chmod +x start_webapp.sh

# Expose port (Railway will map this)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/api/status', timeout=5)"

# Run the application with gunicorn for production
# Use shell form to allow environment variable expansion
# Increased timeout to 600s (10 min) to handle longer enrichment phases
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 600 --access-logfile - --error-logfile - src.web_app:app
