# EdgeWatch Quick Start Guide

## Overview

This guide will help you get EdgeWatch up and running in under 10 minutes.

## Step 1: Install EdgeWatch

### Using Docker (Fastest)

```bash
git clone https://github.com/yourusername/EdgeWatch.git
cd EdgeWatch
docker-compose up -d
```

### Using Python

```bash
git clone https://github.com/yourusername/EdgeWatch.git
cd EdgeWatch
pip install -r requirements.txt
python src/core/daemon.py
```

## Step 2: Verify Installation

Check that EdgeWatch is running:

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "00:01:23",
  "components": {
    "daemon": "running",
    "database": "connected",
    "gossip": "active"
  }
}
```

## Step 3: Access the Dashboard

1. Open your web browser
2. Go to `http://localhost:8080`
3. Login with default credentials:
   - Username: `admin`
   - Password: `admin`
4. **Important:** Change the default password immediately

## Step 4: Configure Your First Monitor

### Add a Node to Monitor

Using the web interface:
1. Navigate to "Nodes" → "Add Node"
2. Enter node details:
   - Name: `edge-server-01`
   - IP Address: `192.168.1.100`
   - Port: `8080`
   - Type: `edge_server`

Using the API:
```bash
curl -X POST http://localhost:8080/api/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "edge-server-01",
    "ip": "192.168.1.100",
    "port": 8080,
    "type": "edge_server"
  }'
```

### Configure Monitoring Rules

Create a basic monitoring rule:
```bash
curl -X POST http://localhost:8080/api/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High CPU Usage",
    "metric": "cpu_usage",
    "threshold": 80,
    "action": "alert"
  }'
```

## Step 5: View Monitoring Data

### Real-time Dashboard

The web dashboard provides:
- Live metrics and graphs
- Node status overview
- Alert notifications
- System health indicators

### API Access

Query current metrics:
```bash
# Get all node metrics
curl http://localhost:8080/api/metrics

# Get specific node data
curl http://localhost:8080/api/nodes/edge-server-01/metrics

# Get historical data
curl http://localhost:8080/api/metrics?start=2024-01-01&end=2024-01-02
```

## Step 6: Set Up Alerts

### Email Notifications

Configure SMTP settings in `config/local.ini`:
```ini
[alerts]
enabled = true
smtp_server = smtp.gmail.com
smtp_port = 587
username = your-email@gmail.com
password = your-app-password
recipients = admin@yourcompany.com
```

### Webhook Notifications

Set up webhook alerts:
```bash
curl -X POST http://localhost:8080/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/your-webhook-url",
    "events": ["high_cpu", "node_down"],
    "format": "slack"
  }'
```

## Step 7: Scale Your Deployment

### Add More Nodes

EdgeWatch automatically discovers and monitors new nodes:

```bash
# Add multiple nodes
for i in {101..110}; do
  curl -X POST http://localhost:8080/api/nodes \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"edge-server-${i}\",
      \"ip\": \"192.168.1.${i}\",
      \"port\": 8080,
      \"type\": \"edge_server\"
    }"
done
```

### Enable Gossip Protocol

For distributed monitoring across multiple EdgeWatch instances:

```ini
[gossip]
enabled = true
seeds = 192.168.1.10:8081,192.168.1.11:8081
broadcast_interval = 30
```

## Common Use Cases

### Scenario 1: Monitor Edge Computing Infrastructure

```bash
# Add edge nodes
curl -X POST http://localhost:8080/api/nodes \
  -d '{"name": "edge-01", "ip": "10.0.1.100", "type": "edge_compute"}'

# Set up performance monitoring
curl -X POST http://localhost:8080/api/rules \
  -d '{"name": "Edge Performance", "metric": "response_time", "threshold": 1000}'
```

### Scenario 2: IoT Device Monitoring

```bash
# Add IoT devices
curl -X POST http://localhost:8080/api/nodes \
  -d '{"name": "sensor-01", "ip": "10.0.2.50", "type": "iot_sensor"}'

# Monitor connectivity
curl -X POST http://localhost:8080/api/rules \
  -d '{"name": "Device Connectivity", "metric": "online_status", "threshold": 1}'
```

### Scenario 3: Content Delivery Network

```bash
# Add CDN nodes
curl -X POST http://localhost:8080/api/nodes \
  -d '{"name": "cdn-east", "ip": "203.0.113.1", "type": "cdn_node"}'

# Monitor cache hit rates
curl -X POST http://localhost:8080/api/rules \
  -d '{"name": "Cache Performance", "metric": "cache_hit_ratio", "threshold": 0.8}'
```

## Next Steps

Now that EdgeWatch is running:

1. **Explore the Dashboard:** Familiarize yourself with all available features
2. **Read the User Manual:** Learn about advanced configuration options
3. **Set Up Monitoring:** Configure comprehensive monitoring for your infrastructure
4. **Customize Alerts:** Set up notifications that matter to your operations
5. **Scale Deployment:** Add more nodes and monitoring instances as needed

## Getting Help

- **Documentation:** [Full documentation](../README.md)
- **API Reference:** [API documentation](../api/README.md)
- **Troubleshooting:** [Common issues and solutions](troubleshooting.md)
- **Community:** Submit issues and feature requests on GitHub
