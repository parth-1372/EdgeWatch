# EdgeWatch API Reference

## Overview

The EdgeWatch REST API provides programmatic access to all monitoring functionality. The API is built with FastAPI and follows RESTful conventions.

**Base URL:** `http://localhost:8080/api`
**Version:** v1
**Authentication:** JWT Bearer Token

## Authentication

### Obtain Access Token

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Use Token in Requests

```http
GET /api/nodes
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## Node Management

### List All Nodes

```http
GET /api/nodes
```

**Parameters:**
- `status` (optional): Filter by node status (online, offline, unknown)
- `type` (optional): Filter by node type
- `limit` (optional): Maximum number of results (default: 100)
- `offset` (optional): Number of results to skip (default: 0)

**Response:**
```json
{
  "nodes": [
    {
      "id": 1,
      "name": "edge-server-01",
      "ip_address": "192.168.1.100",
      "port": 8080,
      "node_type": "edge_server",
      "status": "online",
      "last_seen": "2024-01-15T10:30:00Z",
      "metadata": {
        "location": "datacenter-east",
        "capacity": "high"
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### Get Specific Node

```http
GET /api/nodes/{node_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "edge-server-01",
  "ip_address": "192.168.1.100",
  "port": 8080,
  "node_type": "edge_server",
  "status": "online",
  "last_seen": "2024-01-15T10:30:00Z",
  "metadata": {
    "location": "datacenter-east",
    "capacity": "high"
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Create New Node

```http
POST /api/nodes
Content-Type: application/json

{
  "name": "edge-server-02",
  "ip_address": "192.168.1.101",
  "port": 8080,
  "node_type": "edge_server",
  "metadata": {
    "location": "datacenter-west",
    "capacity": "medium"
  }
}
```

**Response:**
```json
{
  "id": 2,
  "name": "edge-server-02",
  "ip_address": "192.168.1.101",
  "port": 8080,
  "node_type": "edge_server",
  "status": "unknown",
  "last_seen": null,
  "metadata": {
    "location": "datacenter-west",
    "capacity": "medium"
  },
  "created_at": "2024-01-15T10:35:00Z"
}
```

### Update Node

```http
PUT /api/nodes/{node_id}
Content-Type: application/json

{
  "name": "edge-server-02-updated",
  "metadata": {
    "location": "datacenter-west",
    "capacity": "high"
  }
}
```

### Delete Node

```http
DELETE /api/nodes/{node_id}
```

**Response:**
```json
{
  "message": "Node deleted successfully"
}
```

## Metrics

### Get Node Metrics

```http
GET /api/nodes/{node_id}/metrics
```

**Parameters:**
- `metric_name` (optional): Filter by specific metric
- `start_time` (optional): Start time (ISO 8601 format)
- `end_time` (optional): End time (ISO 8601 format)
- `aggregation` (optional): Aggregation method (avg, min, max, sum)
- `interval` (optional): Time interval for aggregation (1m, 5m, 1h, 1d)

**Response:**
```json
{
  "node_id": 1,
  "metrics": [
    {
      "metric_name": "cpu_usage",
      "timestamp": "2024-01-15T10:30:00Z",
      "value": 75.5,
      "labels": {
        "core": "0"
      }
    },
    {
      "metric_name": "memory_usage",
      "timestamp": "2024-01-15T10:30:00Z",
      "value": 68.2,
      "labels": {}
    }
  ]
}
```

### Get All Metrics

```http
GET /api/metrics
```

**Parameters:**
- Same as node-specific metrics endpoint
- Additional `node_id` parameter to filter by specific nodes

### Submit Custom Metrics

```http
POST /api/metrics
Content-Type: application/json

{
  "node_id": 1,
  "metrics": [
    {
      "metric_name": "custom_latency",
      "value": 23.5,
      "timestamp": "2024-01-15T10:30:00Z",
      "labels": {
        "endpoint": "/api/data"
      }
    }
  ]
}
```

## Alerts

### List Alerts

```http
GET /api/alerts
```

**Parameters:**
- `status` (optional): Filter by status (active, acknowledged, resolved)
- `severity` (optional): Filter by severity (low, medium, high, critical)
- `node_id` (optional): Filter by specific node
- `start_time` (optional): Start time filter
- `end_time` (optional): End time filter

**Response:**
```json
{
  "alerts": [
    {
      "id": 1,
      "node_id": 1,
      "alert_type": "high_cpu_usage",
      "severity": "high",
      "message": "CPU usage exceeded 80% threshold",
      "acknowledged": false,
      "created_at": "2024-01-15T10:25:00Z",
      "resolved_at": null,
      "metadata": {
        "threshold": 80,
        "actual_value": 85.3
      }
    }
  ],
  "total": 1
}
```

### Get Specific Alert

```http
GET /api/alerts/{alert_id}
```

### Acknowledge Alert

```http
POST /api/alerts/{alert_id}/acknowledge
Content-Type: application/json

{
  "acknowledged_by": "admin",
  "notes": "Investigating high CPU usage"
}
```

### Resolve Alert

```http
POST /api/alerts/{alert_id}/resolve
Content-Type: application/json

{
  "resolved_by": "admin",
  "resolution_notes": "Scaled up resources"
}
```

## Alert Rules

### List Alert Rules

```http
GET /api/rules
```

**Response:**
```json
{
  "rules": [
    {
      "id": 1,
      "name": "High CPU Usage",
      "metric_name": "cpu_usage",
      "operator": "greater_than",
      "threshold": 80,
      "severity": "high",
      "enabled": true,
      "conditions": {
        "duration": "5m",
        "node_types": ["edge_server"]
      },
      "actions": [
        {
          "type": "email",
          "recipients": ["admin@example.com"]
        }
      ]
    }
  ]
}
```

### Create Alert Rule

```http
POST /api/rules
Content-Type: application/json

{
  "name": "Low Memory Available",
  "metric_name": "memory_available",
  "operator": "less_than",
  "threshold": 1000000000,
  "severity": "medium",
  "enabled": true,
  "conditions": {
    "duration": "2m",
    "node_types": ["edge_server", "iot_device"]
  },
  "actions": [
    {
      "type": "webhook",
      "url": "https://hooks.slack.com/webhook-url"
    }
  ]
}
```

### Update Alert Rule

```http
PUT /api/rules/{rule_id}
Content-Type: application/json

{
  "enabled": false,
  "threshold": 85
}
```

### Delete Alert Rule

```http
DELETE /api/rules/{rule_id}
```

## System Information

### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2d 5h 30m",
  "components": {
    "daemon": "running",
    "database": "connected",
    "gossip": "active",
    "api": "running"
  },
  "metrics": {
    "nodes_monitored": 15,
    "active_alerts": 3,
    "metrics_per_second": 120
  }
}
```

### System Stats

```http
GET /api/stats
```

**Response:**
```json
{
  "system": {
    "cpu_usage": 25.5,
    "memory_usage": 45.2,
    "disk_usage": 67.8,
    "network_io": {
      "bytes_sent": 1024000,
      "bytes_received": 2048000
    }
  },
  "edgewatch": {
    "nodes_total": 15,
    "nodes_online": 12,
    "nodes_offline": 3,
    "metrics_collected": 1500000,
    "alerts_generated": 250,
    "database_size": "145MB"
  }
}
```

### Configuration

```http
GET /api/config
```

**Response:**
```json
{
  "network": {
    "port": 8080,
    "host": "0.0.0.0",
    "gossip_port": 8081
  },
  "monitoring": {
    "interval": 30,
    "metrics_retention": "7d",
    "alert_threshold": 0.8
  },
  "features": {
    "gossip_enabled": true,
    "prometheus_enabled": true,
    "dashboard_enabled": true
  }
}
```

## Webhooks

### List Webhooks

```http
GET /api/webhooks
```

### Create Webhook

```http
POST /api/webhooks
Content-Type: application/json

{
  "name": "Slack Notifications",
  "url": "https://hooks.slack.com/services/...",
  "events": ["alert_created", "node_down"],
  "headers": {
    "Content-Type": "application/json"
  },
  "template": {
    "text": "Alert: {{alert.message}} on {{node.name}}"
  },
  "enabled": true
}
```

### Test Webhook

```http
POST /api/webhooks/{webhook_id}/test
```

## Export/Import

### Export Configuration

```http
GET /api/export/config
```

### Export Data

```http
GET /api/export/data
```

**Parameters:**
- `format` (optional): Export format (json, csv, xlsx)
- `start_time` (optional): Start time for data export
- `end_time` (optional): End time for data export
- `nodes` (optional): Comma-separated list of node IDs

### Import Configuration

```http
POST /api/import/config
Content-Type: application/json

{
  "nodes": [...],
  "rules": [...],
  "webhooks": [...]
}
```

## Error Responses

All API endpoints return standard HTTP status codes and error responses:

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": {
    "field": "ip_address",
    "error": "Invalid IP address format"
  }
}
```

### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Node not found",
  "resource_id": "123"
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred",
  "request_id": "req-12345"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Default Rate:** 1000 requests per hour per user
- **Burst Rate:** 100 requests per minute
- **Headers:** Rate limit information is included in response headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642186800
```

## SDK Examples

### Python SDK

```python
import edgewatch

client = edgewatch.Client(
    base_url="http://localhost:8080",
    token="your-access-token"
)

# List nodes
nodes = client.nodes.list()

# Create node
node = client.nodes.create({
    "name": "new-node",
    "ip_address": "192.168.1.200",
    "port": 8080,
    "node_type": "edge_server"
})

# Get metrics
metrics = client.metrics.get_node_metrics(
    node_id=1,
    metric_name="cpu_usage",
    start_time="2024-01-01T00:00:00Z"
)
```

### JavaScript SDK

```javascript
import EdgeWatch from 'edgewatch-js';

const client = new EdgeWatch({
  baseURL: 'http://localhost:8080',
  token: 'your-access-token'
});

// List nodes
const nodes = await client.nodes.list();

// Create alert rule
const rule = await client.rules.create({
  name: 'High Memory Usage',
  metric_name: 'memory_usage',
  operator: 'greater_than',
  threshold: 90,
  severity: 'high'
});
```

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:
- **JSON:** `http://localhost:8080/api/openapi.json`
- **Interactive Docs:** `http://localhost:8080/docs`
- **ReDoc:** `http://localhost:8080/redoc`
