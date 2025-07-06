# EdgeWatch Installation Guide

## Prerequisites

- Python 3.8 or higher
- Docker and Docker Compose (for containerized deployment)
- Git (for source code management)
- Network access to target monitoring infrastructure

## Installation Methods

### Method 1: Docker Deployment (Recommended)

The easiest way to deploy EdgeWatch is using Docker containers:

```bash
# Clone the repository
git clone https://github.com/yourusername/EdgeWatch.git
cd EdgeWatch

# Deploy using Docker Compose
docker-compose up -d
```

This will start:
- EdgeWatch monitoring daemon
- Database (SQLite/PostgreSQL)
- Web dashboard
- Prometheus metrics endpoint
- Grafana dashboards (optional)

### Method 2: Manual Installation

For development or custom deployments:

```bash
# Clone the repository
git clone https://github.com/yourusername/EdgeWatch.git
cd EdgeWatch

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure the system
cp config/default.ini config/local.ini
# Edit config/local.ini with your settings

# Initialize database
python src/storage/database.py

# Start the monitoring daemon
python src/core/daemon.py
```

### Method 3: Production Deployment

For production environments:

```bash
# Use production configuration
docker-compose -f deployment/docker-compose.prod.yml up -d

# Or with custom configuration
docker-compose -f deployment/docker-compose.yml \
  -f deployment/docker-compose.prod.yml \
  -f deployment/docker-compose.monitoring.yml up -d
```

## Configuration

### Basic Configuration

Edit `config/local.ini` or use environment variables:

```ini
[network]
port = 8080
host = 0.0.0.0
gossip_port = 8081

[monitoring]
interval = 30
metrics_retention = 7d
alert_threshold = 0.8

[storage]
database_path = data/edgewatch.db
backup_interval = 1h
```

### Environment Variables

Key environment variables for Docker deployment:

```bash
EDGEWATCH_PORT=8080
EDGEWATCH_HOST=0.0.0.0
EDGEWATCH_DB_PATH=/data/edgewatch.db
EDGEWATCH_LOG_LEVEL=INFO
EDGEWATCH_METRICS_ENABLED=true
```

## Verification

### Check Installation

```bash
# Check if EdgeWatch is running
curl http://localhost:8080/health

# View metrics
curl http://localhost:8080/metrics

# Check logs
docker logs edgewatch-daemon
```

### Access Dashboard

1. Open web browser
2. Navigate to `http://localhost:8080`
3. Login with default credentials (admin/admin)
4. Change default password immediately

## Troubleshooting

### Common Issues

**Port conflicts:**
```bash
# Check port usage
netstat -an | grep 8080
# Change port in configuration if needed
```

**Database issues:**
```bash
# Reset database
rm data/edgewatch.db
python src/storage/database.py
```

**Permission issues:**
```bash
# Fix file permissions
chmod -R 755 data/
chown -R $(whoami) data/
```

### Getting Help

- Check logs: `docker logs edgewatch-daemon`
- Review configuration files
- Consult troubleshooting guide
- Submit issues on GitHub

## Next Steps

- [Quick Start Guide](quickstart.md)
- [Configuration Guide](configuration.md)
- [User Manual](user-manual.md)
