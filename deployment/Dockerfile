# EdgeWatch - Distributed Edge Computing Monitoring Platform
# Production-ready containerization with optimized layers

# Use Python 3.9 slim as base image for optimal size and security
FROM python:3.9-slim

# Set metadata
LABEL maintainer="EdgeWatch Team" \
      description="EdgeWatch - Advanced Edge Computing Monitoring System" \
      version="1.0.0"

# Set working directory
WORKDIR /app

# Set environment variables for optimal Python execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    EDGEWATCH_ENV=production \
    EDGEWATCH_PORT=5000 \
    EDGEWATCH_HOST=0.0.0.0

# Install system dependencies for networking and monitoring
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    wget \
    net-tools \
    procps \
    htop \
    iputils-ping \
    telnet \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies with optimization
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code and configuration
COPY src/ ./src/
COPY config/ ./config/

# Create application directories
RUN mkdir -p /app/data /app/logs /app/temp

# Create non-root user for enhanced security
RUN useradd --create-home --shell /bin/bash --uid 1000 edgewatch && \
    chown -R edgewatch:edgewatch /app && \
    chmod -R 755 /app

# Switch to non-root user
USER edgewatch

# Expose ports for EdgeWatch services
EXPOSE 5000 8080 9090

# Add health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${EDGEWATCH_PORT}/health || exit 1

# Set default command to start EdgeWatch daemon
CMD ["python", "-m", "src.core.edgewatch_daemon"]
