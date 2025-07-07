# EdgeWatch Monitoring Quick Reference

## 🎯 After Running `./deployment/deploy.sh deploy`

### Primary Monitoring Interfaces

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **EdgeWatch Dashboard** | http://localhost:8080 | None | Real-time edge monitoring |
| **Grafana Analytics** | http://localhost:3000 | admin / edgewatch_admin_2025 | Historical data & plots |
| **Prometheus Metrics** | http://localhost:9000 | None | Raw metrics & queries |
| **API Access** | http://localhost:5000 | None | REST API endpoints |
| **Load Balancer** | http://localhost | None | Production access |

### Secondary Node Access
- **Secondary Dashboard**: http://localhost:8081
- **Secondary API**: http://localhost:5001

## 📊 Viewing Results & Plots

### Real-time Monitoring
1. Open http://localhost:8080 for live network status
2. View node health, alerts, and performance metrics
3. Monitor edge device connectivity and status

### Historical Analysis & Plots
1. Open http://localhost:3000 (Grafana)
2. Login with admin/edgewatch_admin_2025
3. Navigate to "EdgeWatch System Overview" dashboard
4. Create custom plots and export data

### Data Export
```bash
# Export via API
curl http://localhost:5000/api/nodes > nodes.json
curl http://localhost:5000/metrics > metrics.txt

# Export from Grafana: Panel menu → Share → Export
```

## 🔧 Quick Commands

```bash
# Check deployment status
docker-compose -f deployment/docker-compose.yml ps

# View service logs
docker logs edgewatch-primary
docker logs edgewatch-grafana

# Restart services
./deployment/deploy.sh restart
```

## 📋 Similar to DEMon Project

EdgeWatch provides equivalent monitoring capabilities to DEMon:
- **Web Interface**: EdgeWatch Dashboard (port 8080) ≈ DEMon Web UI
- **Data Visualization**: Grafana (port 3000) ≈ DEMon Plots
- **Metrics Collection**: Prometheus (port 9000) ≈ DEMon Database
- **API Access**: REST API (port 5000) ≈ DEMon Query Interface

📖 **Full Guide**: [docs/user/monitoring-access.md](docs/user/monitoring-access.md)
