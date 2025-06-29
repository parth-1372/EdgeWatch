"""
EdgeWatch Dashboard API
Comprehensive dashboard endpoints for monitoring and visualization.
Provides real-time metrics, historical data, and system health information.
"""

from flask import Flask, Blueprint, request, jsonify, render_template_string
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from collections import defaultdict, deque


# Create blueprint for dashboard endpoints
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


class DashboardMetrics:
    """Centralized metrics collection and aggregation for dashboard"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.logger = logging.getLogger(f"EdgeWatch.Dashboard.{node_id}")
        
        # Real-time metrics storage
        self.metrics = {
            'system': {
                'cpu_usage': deque(maxlen=100),
                'memory_usage': deque(maxlen=100),
                'disk_usage': deque(maxlen=100),
                'network_io': deque(maxlen=100),
                'uptime': time.time()
            },
            'network': {
                'active_connections': 0,
                'messages_sent': 0,
                'messages_received': 0,
                'data_transferred': 0,
                'latency_samples': deque(maxlen=100)
            },
            'database': {
                'query_count': 0,
                'avg_query_time': 0,
                'connection_pool_size': 0,
                'storage_size': 0
            },
            'gossip': {
                'active_peers': 0,
                'gossip_rounds': 0,
                'data_propagation_time': deque(maxlen=50),
                'consensus_status': 'healthy'
            },
            'errors': {
                'total_errors': 0,
                'error_rate': deque(maxlen=100),
                'critical_errors': 0,
                'recovery_success_rate': 0
            }
        }
        
        # Historical data aggregation
        self.historical_data = {
            'hourly': defaultdict(lambda: defaultdict(list)),
            'daily': defaultdict(lambda: defaultdict(list)),
            'weekly': defaultdict(lambda: defaultdict(list))
        }
        
        # Dashboard alerts
        self.alerts = []
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'error_rate': 0.1,
            'network_latency': 1000.0  # ms
        }
        
    def update_system_metrics(self, cpu: float, memory: float, disk: float, network_io: int):
        """Update system performance metrics"""
        timestamp = time.time()
        self.metrics['system']['cpu_usage'].append((timestamp, cpu))
        self.metrics['system']['memory_usage'].append((timestamp, memory))
        self.metrics['system']['disk_usage'].append((timestamp, disk))
        self.metrics['system']['network_io'].append((timestamp, network_io))
        
        # Check for alerts
        self._check_alerts('cpu_usage', cpu)
        self._check_alerts('memory_usage', memory)
        self._check_alerts('disk_usage', disk)
        
    def update_network_metrics(self, connections: int, msg_sent: int, msg_received: int, 
                             data_transferred: int, latency: float):
        """Update network-related metrics"""
        self.metrics['network']['active_connections'] = connections
        self.metrics['network']['messages_sent'] += msg_sent
        self.metrics['network']['messages_received'] += msg_received
        self.metrics['network']['data_transferred'] += data_transferred
        self.metrics['network']['latency_samples'].append((time.time(), latency))
        
        self._check_alerts('network_latency', latency)
        
    def update_database_metrics(self, query_count: int, avg_query_time: float,
                              pool_size: int, storage_size: int):
        """Update database performance metrics"""
        self.metrics['database']['query_count'] += query_count
        self.metrics['database']['avg_query_time'] = avg_query_time
        self.metrics['database']['connection_pool_size'] = pool_size
        self.metrics['database']['storage_size'] = storage_size
        
    def update_gossip_metrics(self, active_peers: int, gossip_rounds: int,
                            propagation_time: float, consensus_status: str):
        """Update gossip protocol metrics"""
        self.metrics['gossip']['active_peers'] = active_peers
        self.metrics['gossip']['gossip_rounds'] += gossip_rounds
        self.metrics['gossip']['data_propagation_time'].append((time.time(), propagation_time))
        self.metrics['gossip']['consensus_status'] = consensus_status
        
    def update_error_metrics(self, total_errors: int, error_rate: float,
                           critical_errors: int, recovery_rate: float):
        """Update error and recovery metrics"""
        self.metrics['errors']['total_errors'] = total_errors
        self.metrics['errors']['error_rate'].append((time.time(), error_rate))
        self.metrics['errors']['critical_errors'] = critical_errors
        self.metrics['errors']['recovery_success_rate'] = recovery_rate
        
        self._check_alerts('error_rate', error_rate)
        
    def _check_alerts(self, metric_name: str, value: float):
        """Check if metric exceeds threshold and create alert"""
        if metric_name in self.alert_thresholds:
            threshold = self.alert_thresholds[metric_name]
            if value > threshold:
                alert = {
                    'timestamp': time.time(),
                    'metric': metric_name,
                    'value': value,
                    'threshold': threshold,
                    'severity': 'warning' if value < threshold * 1.2 else 'critical',
                    'message': f"{metric_name} ({value:.2f}) exceeds threshold ({threshold:.2f})"
                }
                self.alerts.append(alert)
                
                # Keep only last 100 alerts
                if len(self.alerts) > 100:
                    self.alerts.pop(0)
                    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        current_time = time.time()
        
        # Calculate averages for recent samples
        def get_recent_average(samples, window_seconds=60):
            if not samples:
                return 0.0
            recent = [(t, v) for t, v in samples if current_time - t <= window_seconds]
            return sum(v for _, v in recent) / len(recent) if recent else 0.0
        
        return {
            'node_id': self.node_id,
            'timestamp': current_time,
            'uptime': current_time - self.metrics['system']['uptime'],
            'system': {
                'cpu_usage': get_recent_average(self.metrics['system']['cpu_usage']),
                'memory_usage': get_recent_average(self.metrics['system']['memory_usage']),
                'disk_usage': get_recent_average(self.metrics['system']['disk_usage']),
                'network_io': get_recent_average(self.metrics['system']['network_io']),
            },
            'network': {
                'active_connections': self.metrics['network']['active_connections'],
                'messages_sent': self.metrics['network']['messages_sent'],
                'messages_received': self.metrics['network']['messages_received'],
                'data_transferred': self.metrics['network']['data_transferred'],
                'avg_latency': get_recent_average(self.metrics['network']['latency_samples'])
            },
            'database': self.metrics['database'].copy(),
            'gossip': {
                'active_peers': self.metrics['gossip']['active_peers'],
                'gossip_rounds': self.metrics['gossip']['gossip_rounds'],
                'avg_propagation_time': get_recent_average(self.metrics['gossip']['data_propagation_time']),
                'consensus_status': self.metrics['gossip']['consensus_status']
            },
            'errors': {
                'total_errors': self.metrics['errors']['total_errors'],
                'error_rate': get_recent_average(self.metrics['errors']['error_rate']),
                'critical_errors': self.metrics['errors']['critical_errors'],
                'recovery_success_rate': self.metrics['errors']['recovery_success_rate']
            }
        }
    
    def get_historical_data(self, period: str = 'hourly', hours: int = 24) -> Dict[str, Any]:
        """Get historical metrics data"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Simulate historical data aggregation
        # In a real implementation, this would query actual historical data
        timestamps = []
        current = start_time
        while current <= end_time:
            timestamps.append(current.timestamp())
            if period == 'hourly':
                current += timedelta(hours=1)
            elif period == 'daily':
                current += timedelta(days=1)
            else:
                current += timedelta(minutes=5)
        
        return {
            'period': period,
            'start_time': start_time.timestamp(),
            'end_time': end_time.timestamp(),
            'timestamps': timestamps,
            'metrics': {
                'cpu_usage': [50 + i % 30 for i in range(len(timestamps))],
                'memory_usage': [60 + i % 25 for i in range(len(timestamps))],
                'network_latency': [100 + i % 50 for i in range(len(timestamps))],
                'message_throughput': [1000 + i % 500 for i in range(len(timestamps))]
            }
        }
    
    def get_active_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        return sorted(self.alerts[-limit:], key=lambda x: x['timestamp'], reverse=True)


# Global metrics instance (in a real application, this would be properly managed)
_dashboard_metrics = None


def get_dashboard_metrics() -> DashboardMetrics:
    """Get or create dashboard metrics instance"""
    global _dashboard_metrics
    if _dashboard_metrics is None:
        _dashboard_metrics = DashboardMetrics("default")
    return _dashboard_metrics


@dashboard_bp.route('/')
def dashboard_home():
    """Main dashboard page"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EdgeWatch Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .metric-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #2c3e50; }
            .metric-value { font-size: 24px; font-weight: bold; color: #3498db; }
            .metric-unit { font-size: 14px; color: #7f8c8d; }
            .status-healthy { color: #27ae60; }
            .status-warning { color: #f39c12; }
            .status-critical { color: #e74c3c; }
            .refresh-btn { background-color: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .nav-links { margin: 20px 0; }
            .nav-links a { margin-right: 20px; color: #3498db; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>EdgeWatch System Dashboard</h1>
            <p>Real-time monitoring and system health overview</p>
        </div>
        
        <div class="nav-links">
            <a href="/dashboard/metrics">Real-time Metrics</a>
            <a href="/dashboard/network">Network Status</a>
            <a href="/dashboard/alerts">System Alerts</a>
            <a href="/dashboard/historical">Historical Data</a>
        </div>
        
        <div id="metrics-container">
            <p>Loading metrics...</p>
        </div>
        
        <button class="refresh-btn" onclick="loadMetrics()">Refresh Metrics</button>
        
        <script>
            async function loadMetrics() {
                try {
                    const response = await fetch('/dashboard/api/metrics');
                    const data = await response.json();
                    displayMetrics(data);
                } catch (error) {
                    console.error('Failed to load metrics:', error);
                }
            }
            
            function displayMetrics(data) {
                const container = document.getElementById('metrics-container');
                container.innerHTML = `
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-title">System Health</div>
                            <div class="metric-value status-healthy">Healthy</div>
                            <div class="metric-unit">Uptime: ${Math.floor(data.uptime / 3600)}h ${Math.floor((data.uptime % 3600) / 60)}m</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">CPU Usage</div>
                            <div class="metric-value">${data.system.cpu_usage.toFixed(1)}</div>
                            <div class="metric-unit">%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">Memory Usage</div>
                            <div class="metric-value">${data.system.memory_usage.toFixed(1)}</div>
                            <div class="metric-unit">%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">Active Connections</div>
                            <div class="metric-value">${data.network.active_connections}</div>
                            <div class="metric-unit">connections</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">Messages Processed</div>
                            <div class="metric-value">${data.network.messages_sent + data.network.messages_received}</div>
                            <div class="metric-unit">total</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">Network Latency</div>
                            <div class="metric-value">${data.network.avg_latency.toFixed(1)}</div>
                            <div class="metric-unit">ms</div>
                        </div>
                    </div>
                `;
            }
            
            // Load metrics on page load
            loadMetrics();
            
            // Auto-refresh every 30 seconds
            setInterval(loadMetrics, 30000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)


@dashboard_bp.route('/api/metrics')
def api_metrics():
    """API endpoint for current metrics"""
    metrics = get_dashboard_metrics()
    return jsonify(metrics.get_current_metrics())


@dashboard_bp.route('/api/historical')
def api_historical():
    """API endpoint for historical data"""
    period = request.args.get('period', 'hourly')
    hours = int(request.args.get('hours', 24))
    
    metrics = get_dashboard_metrics()
    historical_data = metrics.get_historical_data(period, hours)
    
    return jsonify(historical_data)


@dashboard_bp.route('/api/alerts')
def api_alerts():
    """API endpoint for system alerts"""
    limit = int(request.args.get('limit', 50))
    
    metrics = get_dashboard_metrics()
    alerts = metrics.get_active_alerts(limit)
    
    return jsonify({
        'alerts': alerts,
        'total_count': len(alerts),
        'critical_count': len([a for a in alerts if a['severity'] == 'critical']),
        'warning_count': len([a for a in alerts if a['severity'] == 'warning'])
    })


@dashboard_bp.route('/network')
def network_status():
    """Network status page"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EdgeWatch - Network Status</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .network-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .network-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .peer-list { max-height: 300px; overflow-y: auto; }
            .peer-item { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
            .status-online { color: #27ae60; }
            .status-offline { color: #e74c3c; }
            .back-link { color: #3498db; text-decoration: none; margin-bottom: 20px; display: inline-block; }
        </style>
    </head>
    <body>
        <a href="/dashboard" class="back-link">← Back to Dashboard</a>
        
        <div class="header">
            <h1>Network Status</h1>
            <p>Real-time network connectivity and peer information</p>
        </div>
        
        <div class="network-grid">
            <div class="network-card">
                <h3>Connection Statistics</h3>
                <div id="connection-stats">Loading...</div>
            </div>
            
            <div class="network-card">
                <h3>Active Peers</h3>
                <div id="peer-list" class="peer-list">Loading...</div>
            </div>
        </div>
        
        <script>
            async function loadNetworkStatus() {
                try {
                    const response = await fetch('/dashboard/api/metrics');
                    const data = await response.json();
                    
                    document.getElementById('connection-stats').innerHTML = `
                        <p><strong>Active Connections:</strong> ${data.network.active_connections}</p>
                        <p><strong>Messages Sent:</strong> ${data.network.messages_sent}</p>
                        <p><strong>Messages Received:</strong> ${data.network.messages_received}</p>
                        <p><strong>Data Transferred:</strong> ${(data.network.data_transferred / 1024 / 1024).toFixed(2)} MB</p>
                        <p><strong>Average Latency:</strong> ${data.network.avg_latency.toFixed(1)} ms</p>
                        <p><strong>Gossip Peers:</strong> ${data.gossip.active_peers}</p>
                    `;
                    
                    // Mock peer data
                    const peers = [
                        {id: 'node-001', status: 'online', latency: 45},
                        {id: 'node-002', status: 'online', latency: 78},
                        {id: 'node-003', status: 'offline', latency: 0},
                        {id: 'node-004', status: 'online', latency: 123}
                    ];
                    
                    document.getElementById('peer-list').innerHTML = peers.map(peer => `
                        <div class="peer-item">
                            <span>${peer.id}</span>
                            <span class="status-${peer.status}">${peer.status} ${peer.latency > 0 ? '(' + peer.latency + 'ms)' : ''}</span>
                        </div>
                    `).join('');
                    
                } catch (error) {
                    console.error('Failed to load network status:', error);
                }
            }
            
            loadNetworkStatus();
            setInterval(loadNetworkStatus, 15000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)


@dashboard_bp.route('/alerts')
def alerts_page():
    """System alerts page"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EdgeWatch - System Alerts</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .alerts-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .alert-item { padding: 15px; border-left: 4px solid; margin-bottom: 10px; border-radius: 4px; }
            .alert-critical { border-left-color: #e74c3c; background-color: #fdf2f2; }
            .alert-warning { border-left-color: #f39c12; background-color: #fefaf6; }
            .alert-info { border-left-color: #3498db; background-color: #f6f9fc; }
            .alert-timestamp { font-size: 12px; color: #7f8c8d; }
            .alert-message { font-weight: bold; margin: 5px 0; }
            .alert-details { font-size: 14px; color: #5a6c7d; }
            .back-link { color: #3498db; text-decoration: none; margin-bottom: 20px; display: inline-block; }
            .alert-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px; }
            .summary-card { background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <a href="/dashboard" class="back-link">← Back to Dashboard</a>
        
        <div class="header">
            <h1>System Alerts</h1>
            <p>Monitor system warnings and critical issues</p>
        </div>
        
        <div id="alert-summary" class="alert-summary">Loading...</div>
        
        <div class="alerts-container">
            <h3>Recent Alerts</h3>
            <div id="alerts-list">Loading alerts...</div>
        </div>
        
        <script>
            async function loadAlerts() {
                try {
                    const response = await fetch('/dashboard/api/alerts');
                    const data = await response.json();
                    
                    document.getElementById('alert-summary').innerHTML = `
                        <div class="summary-card">
                            <h3>${data.total_count}</h3>
                            <p>Total Alerts</p>
                        </div>
                        <div class="summary-card">
                            <h3>${data.critical_count}</h3>
                            <p>Critical</p>
                        </div>
                        <div class="summary-card">
                            <h3>${data.warning_count}</h3>
                            <p>Warnings</p>
                        </div>
                    `;
                    
                    if (data.alerts.length === 0) {
                        document.getElementById('alerts-list').innerHTML = '<p>No recent alerts</p>';
                    } else {
                        document.getElementById('alerts-list').innerHTML = data.alerts.map(alert => `
                            <div class="alert-item alert-${alert.severity}">
                                <div class="alert-timestamp">${new Date(alert.timestamp * 1000).toLocaleString()}</div>
                                <div class="alert-message">${alert.message}</div>
                                <div class="alert-details">Metric: ${alert.metric} | Value: ${alert.value} | Threshold: ${alert.threshold}</div>
                            </div>
                        `).join('');
                    }
                    
                } catch (error) {
                    console.error('Failed to load alerts:', error);
                }
            }
            
            loadAlerts();
            setInterval(loadAlerts, 30000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)


@dashboard_bp.route('/historical')
def historical_page():
    """Historical data visualization page"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EdgeWatch - Historical Data</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .controls { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .back-link { color: #3498db; text-decoration: none; margin-bottom: 20px; display: inline-block; }
            select, button { padding: 8px 12px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
            button { background-color: #3498db; color: white; cursor: pointer; }
            .chart-placeholder { height: 300px; display: flex; align-items: center; justify-content: center; background-color: #f8f9fa; border: 2px dashed #dee2e6; border-radius: 8px; }
        </style>
    </head>
    <body>
        <a href="/dashboard" class="back-link">← Back to Dashboard</a>
        
        <div class="header">
            <h1>Historical Data</h1>
            <p>View system performance trends over time</p>
        </div>
        
        <div class="controls">
            <label>Time Period:</label>
            <select id="period-select">
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
            </select>
            
            <label>Duration:</label>
            <select id="duration-select">
                <option value="6">6 hours</option>
                <option value="24" selected>24 hours</option>
                <option value="72">3 days</option>
                <option value="168">1 week</option>
            </select>
            
            <button onclick="loadHistoricalData()">Update Chart</button>
        </div>
        
        <div class="chart-container">
            <h3>System Performance Trends</h3>
            <div id="chart-area" class="chart-placeholder">
                <p>Chart visualization would be displayed here<br/>
                (Integration with Chart.js or similar library recommended)</p>
            </div>
        </div>
        
        <script>
            async function loadHistoricalData() {
                const period = document.getElementById('period-select').value;
                const hours = document.getElementById('duration-select').value;
                
                try {
                    const response = await fetch(`/dashboard/api/historical?period=${period}&hours=${hours}`);
                    const data = await response.json();
                    
                    // In a real implementation, you would use a charting library like Chart.js
                    document.getElementById('chart-area').innerHTML = `
                        <div style="text-align: left; padding: 20px;">
                            <h4>Historical Data Summary</h4>
                            <p><strong>Period:</strong> ${data.period}</p>
                            <p><strong>Time Range:</strong> ${new Date(data.start_time * 1000).toLocaleString()} - ${new Date(data.end_time * 1000).toLocaleString()}</p>
                            <p><strong>Data Points:</strong> ${data.timestamps.length}</p>
                            <p><strong>Avg CPU Usage:</strong> ${(data.metrics.cpu_usage.reduce((a, b) => a + b, 0) / data.metrics.cpu_usage.length).toFixed(1)}%</p>
                            <p><strong>Avg Memory Usage:</strong> ${(data.metrics.memory_usage.reduce((a, b) => a + b, 0) / data.metrics.memory_usage.length).toFixed(1)}%</p>
                            <p><strong>Avg Network Latency:</strong> ${(data.metrics.network_latency.reduce((a, b) => a + b, 0) / data.metrics.network_latency.length).toFixed(1)}ms</p>
                            <p><em>Note: This is a simplified view. A full implementation would include interactive charts.</em></p>
                        </div>
                    `;
                    
                } catch (error) {
                    console.error('Failed to load historical data:', error);
                    document.getElementById('chart-area').innerHTML = '<p>Error loading historical data</p>';
                }
            }
            
            // Load initial data
            loadHistoricalData();
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)


@dashboard_bp.route('/api/nodes')
def api_nodes():
    """API endpoint for node information"""
    # Mock node data - in real implementation, this would query actual nodes
    nodes = [
        {
            'id': 'edge-node-001',
            'status': 'online',
            'location': 'New York, NY',
            'cpu_usage': 45.2,
            'memory_usage': 67.8,
            'uptime': 3600 * 48,  # 48 hours
            'connections': 12,
            'last_seen': time.time() - 30
        },
        {
            'id': 'edge-node-002',
            'status': 'online',
            'location': 'Los Angeles, CA',
            'cpu_usage': 32.1,
            'memory_usage': 54.3,
            'uptime': 3600 * 24,  # 24 hours
            'connections': 8,
            'last_seen': time.time() - 45
        },
        {
            'id': 'edge-node-003',
            'status': 'warning',
            'location': 'Chicago, IL',
            'cpu_usage': 85.7,
            'memory_usage': 92.1,
            'uptime': 3600 * 12,  # 12 hours
            'connections': 3,
            'last_seen': time.time() - 120
        }
    ]
    
    return jsonify({
        'nodes': nodes,
        'total_nodes': len(nodes),
        'online_nodes': len([n for n in nodes if n['status'] == 'online']),
        'warning_nodes': len([n for n in nodes if n['status'] == 'warning']),
        'offline_nodes': len([n for n in nodes if n['status'] == 'offline'])
    })


def init_dashboard_metrics(app, node_id: str, config: Optional[Dict[str, Any]] = None):
    """Initialize dashboard metrics for the application"""
    global _dashboard_metrics
    _dashboard_metrics = DashboardMetrics(node_id)
    
    # Register blueprint
    app.register_blueprint(dashboard_bp)
    
    # Start metrics collection (in a real app, this would be more sophisticated)
    import threading
    import random
    
    def update_mock_metrics():
        """Update metrics with mock data for demonstration"""
        while True:
            try:
                _dashboard_metrics.update_system_metrics(
                    cpu=random.uniform(20, 80),
                    memory=random.uniform(40, 90),
                    disk=random.uniform(30, 70),
                    network_io=random.randint(1000, 50000)
                )
                
                _dashboard_metrics.update_network_metrics(
                    connections=random.randint(5, 25),
                    msg_sent=random.randint(10, 100),
                    msg_received=random.randint(10, 100),
                    data_transferred=random.randint(1024, 1024*1024),
                    latency=random.uniform(50, 200)
                )
                
                _dashboard_metrics.update_gossip_metrics(
                    active_peers=random.randint(3, 15),
                    gossip_rounds=random.randint(1, 5),
                    propagation_time=random.uniform(100, 500),
                    consensus_status=random.choice(['healthy', 'degraded', 'recovering'])
                )
                
                _dashboard_metrics.update_error_metrics(
                    total_errors=random.randint(0, 50),
                    error_rate=random.uniform(0, 0.05),
                    critical_errors=random.randint(0, 3),
                    recovery_rate=random.uniform(0.8, 1.0)
                )
                
                time.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logging.error(f"Error updating dashboard metrics: {e}")
                time.sleep(60)
    
    # Start background metrics updater
    metrics_thread = threading.Thread(target=update_mock_metrics, daemon=True)
    metrics_thread.start()
    
    return _dashboard_metrics
