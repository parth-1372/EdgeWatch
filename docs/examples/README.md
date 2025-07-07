# EdgeWatch Examples

## Basic Examples

### 1. Simple Node Monitoring

Monitor a single edge server:

```bash
# Add node via API
curl -X POST http://localhost:8080/api/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "edge-server-01",
    "ip_address": "192.168.1.100",
    "port": 8080,
    "node_type": "edge_server",
    "location": "Building A, Floor 2"
  }'

# Set up basic monitoring
curl -X POST http://localhost:8080/api/monitors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Basic System Monitor",
    "node_id": "edge-server-01",
    "metrics": ["cpu_usage", "memory_usage", "disk_usage"],
    "interval": 30
  }'
```

### 2. Multi-Node Deployment

Deploy EdgeWatch across multiple nodes:

```bash
# Deploy to primary node
./deployment/deploy.sh deploy

# Configure secondary nodes
for node in 192.168.1.101 192.168.1.102 192.168.1.103; do
  ssh $node "
    git clone https://github.com/your-org/edgewatch.git
    cd edgewatch
    cp config/default.ini config/production.ini
    sed -i 's/seeds = .*/seeds = 192.168.1.100:8081/' config/production.ini
    ./deployment/deploy.sh deploy
  "
done
```

## Real-World Scenarios

### 3. IoT Sensor Network

Monitor IoT devices across multiple locations:

```python
# Add IoT devices programmatically
import requests

devices = [
    {"name": "temp-sensor-01", "ip": "10.0.1.50", "type": "temperature"},
    {"name": "humid-sensor-01", "ip": "10.0.1.51", "type": "humidity"},
    {"name": "motion-sensor-01", "ip": "10.0.1.52", "type": "motion"}
]

for device in devices:
    response = requests.post(
        "http://localhost:8080/api/nodes",
        json={
            "name": device["name"],
            "ip_address": device["ip"],
            "node_type": "iot_sensor",
            "metadata": {"sensor_type": device["type"]}
        }
    )
    print(f"Added {device['name']}: {response.status_code}")

# Configure IoT-specific monitoring
iot_monitor = {
    "name": "IoT Connectivity Monitor",
    "node_filter": {"node_type": "iot_sensor"},
    "metrics": ["online_status", "battery_level", "signal_strength"],
    "interval": 60,
    "alert_rules": [
        {"metric": "battery_level", "threshold": 20, "operator": "lt"},
        {"metric": "signal_strength", "threshold": -80, "operator": "lt"}
    ]
}

requests.post("http://localhost:8080/api/monitors", json=iot_monitor)
```

### 4. Edge Computing Cluster

Set up monitoring for edge computing workloads:

```yaml
# kubernetes-monitoring.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: edgewatch-config
data:
  production.ini: |
    [network]
    port = 8080
    gossip_port = 8081
    
    [monitoring]
    interval = 30
    kubernetes_enabled = true
    
    [alerts]
    enabled = true
    webhook_url = https://hooks.slack.com/your-webhook
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: edgewatch-agent
spec:
  selector:
    matchLabels:
      app: edgewatch-agent
  template:
    metadata:
      labels:
        app: edgewatch-agent
    spec:
      containers:
      - name: edgewatch
        image: edgewatch:latest
        ports:
        - containerPort: 8080
        - containerPort: 8081
        volumeMounts:
        - name: config
          mountPath: /app/config
        env:
        - name: EDGEWATCH_CLUSTER_MODE
          value: "enabled"
        - name: EDGEWATCH_NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
      volumes:
      - name: config
        configMap:
          name: edgewatch-config
```

### 5. Content Delivery Network (CDN)

Monitor CDN performance across edge locations:

```bash
# Add CDN edge nodes
locations=(
    "us-east-1:203.0.113.1"
    "us-west-1:203.0.113.2"
    "eu-west-1:203.0.113.3"
    "ap-south-1:203.0.113.4"
)

for location in "${locations[@]}"; do
    IFS=':' read -r region ip <<< "$location"
    curl -X POST http://localhost:8080/api/nodes \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"cdn-${region}\",
        \"ip_address\": \"${ip}\",
        \"node_type\": \"cdn_node\",
        \"metadata\": {
          \"region\": \"${region}\",
          \"role\": \"edge_cache\"
        }
      }"
done

# Configure CDN-specific monitoring
curl -X POST http://localhost:8080/api/monitors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CDN Performance Monitor",
    "node_filter": {"node_type": "cdn_node"},
    "metrics": [
      "cache_hit_ratio",
      "response_time",
      "bandwidth_usage",
      "storage_usage"
    ],
    "interval": 15,
    "alert_rules": [
      {"metric": "cache_hit_ratio", "threshold": 0.8, "operator": "lt"},
      {"metric": "response_time", "threshold": 500, "operator": "gt"}
    ]
  }'
```

## Advanced Configurations

### 6. Custom Metrics Integration

Integrate application-specific metrics:

```python
# custom_metrics_exporter.py
from flask import Flask, jsonify
import psutil
import time

app = Flask(__name__)

@app.route('/metrics')
def custom_metrics():
    """Custom metrics endpoint for EdgeWatch"""
    metrics = {
        "timestamp": time.time(),
        "custom_metrics": {
            "app_response_time": get_app_response_time(),
            "active_users": get_active_users(),
            "queue_length": get_queue_length(),
            "error_rate": get_error_rate()
        },
        "system_metrics": {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
    }
    return jsonify(metrics)

def get_app_response_time():
    # Your application logic here
    return 0.245

def get_active_users():
    # Your application logic here
    return 157

def get_queue_length():
    # Your application logic here
    return 23

def get_error_rate():
    # Your application logic here
    return 0.01

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9090)
```

### 7. Automated Deployment with Ansible

```yaml
# ansible/deploy-edgewatch.yml
- name: Deploy EdgeWatch to edge nodes
  hosts: edge_nodes
  become: yes
  vars:
    edgewatch_version: "latest"
    primary_node: "192.168.1.100"
    
  tasks:
    - name: Install Docker
      apt:
        name: docker.io
        state: present
        update_cache: yes
        
    - name: Install Docker Compose
      pip:
        name: docker-compose
        state: present
        
    - name: Clone EdgeWatch repository
      git:
        repo: https://github.com/your-org/edgewatch.git
        dest: /opt/edgewatch
        version: main
        
    - name: Configure EdgeWatch
      template:
        src: production.ini.j2
        dest: /opt/edgewatch/config/production.ini
        
    - name: Deploy EdgeWatch
      shell: |
        cd /opt/edgewatch
        ./deployment/deploy.sh deploy
      environment:
        EDGEWATCH_VERSION: "{{ edgewatch_version }}"
        
    - name: Verify deployment
      uri:
        url: "http://{{ ansible_default_ipv4.address }}:5000/health"
        method: GET
      retries: 5
      delay: 10
```

### 8. High Availability Setup

Configure EdgeWatch for high availability:

```bash
# ha-setup.sh
#!/bin/bash

# Primary cluster setup
PRIMARY_NODES=(
    "192.168.1.100"
    "192.168.1.101" 
    "192.168.1.102"
)

# Configure primary cluster
for i in "${!PRIMARY_NODES[@]}"; do
    node="${PRIMARY_NODES[$i]}"
    ssh "$node" "
        cd /opt/edgewatch
        cp config/default.ini config/production.ini
        
        # Configure as primary node
        sed -i 's/cluster_mode = .*/cluster_mode = enabled/' config/production.ini
        sed -i 's/node_role = .*/node_role = primary/' config/production.ini
        sed -i 's/node_id = .*/node_id = primary-$i/' config/production.ini
        
        # Set gossip seeds (all primary nodes)
        seeds=$(IFS=':8081,'; echo '${PRIMARY_NODES[*]:8081}')
        sed -i \"s/seeds = .*/seeds = \$seeds/\" config/production.ini
        
        # Deploy
        ./deployment/deploy.sh deploy
    "
done

# Health check
echo "Checking cluster health..."
for node in "${PRIMARY_NODES[@]}"; do
    if curl -f "http://$node:5000/health" >/dev/null 2>&1; then
        echo "✓ $node is healthy"
    else
        echo "✗ $node is not responding"
    fi
done
```

### 9. Monitoring Dashboard Automation

Automate dashboard creation:

```python
# dashboard_automation.py
import requests
import json

# EdgeWatch API configuration
API_BASE = "http://localhost:8080/api"
GRAFANA_BASE = "http://localhost:3000/api"
GRAFANA_TOKEN = "your-grafana-token"

def create_monitoring_dashboard():
    """Create comprehensive monitoring dashboard"""
    
    # Dashboard configuration
    dashboard = {
        "dashboard": {
            "title": "EdgeWatch Overview",
            "panels": [
                {
                    "title": "System Overview",
                    "type": "stat",
                    "targets": [
                        {"expr": "edgewatch_nodes_total"},
                        {"expr": "edgewatch_nodes_online"},
                        {"expr": "edgewatch_alerts_active"}
                    ]
                },
                {
                    "title": "Node Health",
                    "type": "table",
                    "targets": [
                        {"expr": "edgewatch_node_health"}
                    ]
                },
                {
                    "title": "Network Topology",
                    "type": "graph",
                    "targets": [
                        {"expr": "edgewatch_gossip_connections"}
                    ]
                }
            ]
        },
        "overwrite": True
    }
    
    # Create dashboard
    headers = {
        "Authorization": f"Bearer {GRAFANA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{GRAFANA_BASE}/dashboards/db",
        headers=headers,
        json=dashboard
    )
    
    if response.status_code == 200:
        print("Dashboard created successfully")
    else:
        print(f"Failed to create dashboard: {response.text}")

def setup_alerting_rules():
    """Configure alerting rules"""
    
    alert_rules = [
        {
            "name": "Node Down",
            "metric": "node_online",
            "threshold": 1,
            "operator": "lt",
            "severity": "critical",
            "notification_channels": ["email", "slack"]
        },
        {
            "name": "High CPU Usage",
            "metric": "cpu_usage",
            "threshold": 80,
            "operator": "gt", 
            "severity": "warning",
            "notification_channels": ["email"]
        },
        {
            "name": "Low Disk Space",
            "metric": "disk_usage",
            "threshold": 90,
            "operator": "gt",
            "severity": "warning",
            "notification_channels": ["email", "slack"]
        }
    ]
    
    for rule in alert_rules:
        response = requests.post(f"{API_BASE}/alerts", json=rule)
        if response.status_code == 201:
            print(f"Alert rule '{rule['name']}' created")
        else:
            print(f"Failed to create alert rule: {response.text}")

if __name__ == "__main__":
    create_monitoring_dashboard()
    setup_alerting_rules()
    print("Monitoring setup completed!")
```

### 10. Performance Optimization

Optimize EdgeWatch for high-performance environments:

```bash
# performance-tuning.sh
#!/bin/bash

echo "Applying EdgeWatch performance optimizations..."

# System-level optimizations
echo "Configuring system parameters..."
cat > /etc/sysctl.d/99-edgewatch.conf << EOF
# Network optimizations
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 16384 16777216

# File descriptor limits
fs.file-max = 1000000

# Memory settings
vm.swappiness = 10
vm.dirty_ratio = 80
vm.dirty_background_ratio = 5
EOF

sysctl -p /etc/sysctl.d/99-edgewatch.conf

# Docker optimizations
echo "Optimizing Docker settings..."
cat > /etc/docker/daemon.json << EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ]
}
EOF

systemctl restart docker

# EdgeWatch configuration optimizations
echo "Tuning EdgeWatch configuration..."
cat >> config/production.ini << EOF
[performance]
# Reduce monitoring frequency for stable nodes
adaptive_intervals = true
min_interval = 60
max_interval = 300

# Optimize gossip protocol
gossip_fanout = 3
gossip_interval = 30
max_gossip_packet_size = 1400

# Database optimizations
db_connection_pool = 20
db_query_timeout = 30

# Memory management
gc_interval = 300
max_memory_usage = 80
EOF

echo "Performance optimizations applied!"
echo "Restart EdgeWatch to apply changes:"
echo "./deployment/deploy.sh restart"
```

## Testing Examples

### 11. Load Testing

Test EdgeWatch under load:

```python
# load_test.py
import asyncio
import aiohttp
import time
import random

async def simulate_node_data(session, node_id):
    """Simulate data from a monitoring node"""
    
    while True:
        # Generate realistic metrics
        data = {
            "node_id": node_id,
            "timestamp": time.time(),
            "metrics": {
                "cpu_usage": random.uniform(10, 90),
                "memory_usage": random.uniform(20, 80),
                "disk_usage": random.uniform(30, 70),
                "network_rx": random.randint(1000, 10000),
                "network_tx": random.randint(1000, 10000)
            }
        }
        
        try:
            async with session.post(
                "http://localhost:8080/api/metrics",
                json=data
            ) as response:
                if response.status != 200:
                    print(f"Error from node {node_id}: {response.status}")
        except Exception as e:
            print(f"Connection error for node {node_id}: {e}")
        
        # Random interval between 15-45 seconds
        await asyncio.sleep(random.uniform(15, 45))

async def main():
    """Run load test with multiple simulated nodes"""
    
    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        
        # Simulate 100 nodes
        tasks = []
        for i in range(100):
            node_id = f"load-test-node-{i:03d}"
            task = asyncio.create_task(simulate_node_data(session, node_id))
            tasks.append(task)
        
        print("Starting load test with 100 simulated nodes...")
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

### 12. Failover Testing

Test EdgeWatch resilience:

```bash
# failover-test.sh
#!/bin/bash

echo "Starting EdgeWatch failover test..."

# Get list of active nodes
NODES=($(curl -s http://localhost:8080/api/nodes | jq -r '.[].ip_address'))

echo "Found ${#NODES[@]} active nodes"

# Test 1: Primary node failure
echo "Testing primary node failure..."
PRIMARY_NODE="${NODES[0]}"

# Simulate network partition
sudo iptables -A INPUT -s "$PRIMARY_NODE" -j DROP
sudo iptables -A OUTPUT -d "$PRIMARY_NODE" -j DROP

echo "Network partition created for $PRIMARY_NODE"

# Wait for failover detection
sleep 60

# Check cluster status
curl -s http://localhost:8080/api/cluster/status | jq

# Restore network
sudo iptables -D INPUT -s "$PRIMARY_NODE" -j DROP
sudo iptables -D OUTPUT -d "$PRIMARY_NODE" -j DROP

echo "Network partition removed"

# Test 2: Database failure
echo "Testing database failover..."
docker-compose stop edgewatch-database

# Wait for database failover
sleep 30

# Check status
curl -s http://localhost:8080/api/health/database

# Restore database
docker-compose start edgewatch-database

echo "Failover test completed"
```

---

These examples demonstrate EdgeWatch's flexibility and power across various deployment scenarios. Start with the basic examples and gradually implement more advanced configurations as your needs grow.

For more detailed examples, see the [API Reference](../api/reference.md) and [Developer Guide](../developer/development.md).
