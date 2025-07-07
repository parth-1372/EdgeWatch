# Accessing EdgeWatch Monitoring Results and Plots

After successfully deploying EdgeWatch using the `deployment/deploy.sh` script, you can access various monitoring dashboards and visualization tools through your web browser. This guide explains where to find monitoring results, plots, and real-time data similar to the DEMon project.

## Quick Access URLs (After Deployment)

Once all services are running, you can access the following interfaces:

### 1. EdgeWatch Main Dashboard
- **URL**: http://localhost:8080 (Primary Node) or http://localhost:8081 (Secondary Node)
- **Purpose**: Real-time edge monitoring dashboard with network topology, node status, and alerts
- **Features**: 
  - Live network graph visualization
  - Node health indicators
  - Performance metrics charts
  - Alert management
  - Edge device status monitoring

### 2. Grafana Visualization Dashboard
- **URL**: http://localhost:3000
- **Login**: 
  - Username: `admin`
  - Password: `edgewatch_admin_2025`
- **Purpose**: Advanced monitoring dashboards with historical data and analytics
- **Features**:
  - System performance graphs (CPU, memory, network)
  - Custom EdgeWatch metrics dashboards
  - Historical trend analysis
  - Alerting and notification management
  - Exportable charts and reports

### 3. Prometheus Metrics Interface
- **URL**: http://localhost:9000
- **Purpose**: Raw metrics collection and query interface
- **Features**:
  - PromQL query interface for custom metrics
  - Raw metrics data exploration
  - Service discovery status
  - Target health monitoring

### 4. EdgeWatch API Endpoints
- **Primary Node API**: http://localhost:5000
- **Secondary Node API**: http://localhost:5001
- **Purpose**: REST API for programmatic access to monitoring data
- **Key Endpoints**:
  - `/health` - System health check
  - `/metrics` - Prometheus metrics endpoint
  - `/api/nodes` - Node status information
  - `/api/network` - Network topology data
  - `/api/alerts` - Active alerts and notifications

### 5. Load Balanced Interface (via Nginx)
- **URL**: http://localhost (port 80)
- **Purpose**: Production-ready load-balanced access to EdgeWatch services
- **Features**: SSL termination, load balancing, and high availability

## Viewing Monitoring Results

### Real-time Monitoring
1. **Primary Dashboard**: Visit http://localhost:8080 for the main EdgeWatch interface
   - View network topology graph
   - Monitor node status in real-time
   - Check system alerts and notifications
   - Access performance metrics

2. **Grafana Dashboards**: Visit http://localhost:3000
   - Login with admin credentials
   - Navigate to "Dashboards" → "EdgeWatch System Overview"
   - View detailed performance charts and graphs
   - Create custom dashboards for specific metrics

### Historical Data and Plots
1. **Performance Trends**: Use Grafana to view historical performance data
   - CPU and memory usage over time
   - Network latency and throughput trends
   - Edge device availability statistics
   - Alert frequency and patterns

2. **Custom Queries**: Use Prometheus at http://localhost:9000
   - Write PromQL queries for specific metrics
   - Export data for external analysis
   - Create custom visualizations

### Exporting Data and Plots

#### From Grafana:
1. Navigate to any dashboard panel
2. Click the panel menu (three dots)
3. Select "Share" → "Export" → "Save as image/PDF"
4. Or use "Share" → "Snapshot" for shareable links

#### From Prometheus:
1. Use the query interface to select metrics
2. Export data as CSV or JSON via the API
3. Use `/api/v1/query_range` endpoint for time-series data

#### Via EdgeWatch API:
```bash
# Export node data
curl http://localhost:5000/api/nodes > nodes_data.json

# Export metrics data
curl http://localhost:5000/metrics > metrics_data.txt

# Export network topology
curl http://localhost:5000/api/network > network_topology.json
```

## Monitoring Workflow

### 1. Daily Monitoring
- Check http://localhost:8080 for system overview
- Review alerts and notifications
- Monitor node health indicators

### 2. Performance Analysis
- Use Grafana dashboards for detailed metrics analysis
- Review historical trends for capacity planning
- Investigate performance anomalies

### 3. Troubleshooting
- Check Prometheus targets at http://localhost:9000/targets
- Review logs in Grafana or via Docker logs
- Use API endpoints for detailed system information

## Creating Custom Plots and Dashboards

### In Grafana:
1. Login to http://localhost:3000
2. Click "+" → "Dashboard"
3. Add panels with EdgeWatch metrics
4. Use data source: "EdgeWatch Prometheus"
5. Write PromQL queries for specific metrics

### Common EdgeWatch Metrics:
- `edgewatch_node_status` - Node health status
- `edgewatch_network_latency` - Network latency measurements
- `edgewatch_cpu_usage` - CPU utilization per node
- `edgewatch_memory_usage` - Memory consumption
- `edgewatch_alert_count` - Active alert count

## Comparison with DEMon

Similar to DEMon's monitoring capabilities, EdgeWatch provides:

- **Real-time Dashboards**: Like DEMon's web interface, accessible at port 8080
- **Historical Analysis**: Grafana dashboards similar to DEMon's plotting functionality
- **Data Export**: API endpoints for exporting monitoring data
- **Performance Metrics**: CPU, memory, network monitoring like DEMon's system metrics
- **Alert Management**: Centralized alerting system

## Troubleshooting Access Issues

If you cannot access the interfaces:

1. **Check Service Status**:
   ```bash
   docker-compose -f deployment/docker-compose.yml ps
   ```

2. **Verify Port Availability**:
   ```bash
   netstat -an | findstr "3000 8080 9000"
   ```

3. **Check Container Logs**:
   ```bash
   docker logs edgewatch-grafana
   docker logs edgewatch-prometheus
   docker logs edgewatch-primary
   ```

4. **Restart Services if Needed**:
   ```bash
   cd deployment
   ./deploy.sh restart
   ```

## Next Steps

After accessing the monitoring interfaces:
1. Explore the pre-configured Grafana dashboards
2. Set up custom alerts and notifications
3. Create specific dashboards for your use case
4. Export historical data for analysis
5. Configure additional monitoring targets as needed

For detailed API documentation, visit the EdgeWatch API reference at `/docs/api/reference.md`.
