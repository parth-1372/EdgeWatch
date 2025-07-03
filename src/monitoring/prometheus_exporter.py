"""
EdgeWatch Prometheus Integration
Custom metrics export and Prometheus integration
"""

import time
from typing import Dict, List, Any, Optional
from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, generate_latest
from prometheus_client.exposition import MetricsHandler
import threading
import logging
from datetime import datetime
from http.server import HTTPServer

from ..core.config_manager import ConfigManager
from ..monitoring.metrics_collector import MetricsCollector


class PrometheusExporter:
    """Prometheus metrics exporter for EdgeWatch"""
    
    def __init__(self, config_manager: ConfigManager, metrics_collector: MetricsCollector):
        self.config = config_manager
        self.metrics_collector = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Create custom registry
        self.registry = CollectorRegistry()
        
        # Initialize Prometheus metrics
        self._init_prometheus_metrics()
        
        # HTTP server for metrics endpoint
        self._server = None
        self._server_thread = None
        self._running = False
        
        # Configuration
        self.port = self.config.get('prometheus.port', 9090)
        self.host = self.config.get('prometheus.host', '0.0.0.0')
        self.update_interval = self.config.get('prometheus.update_interval', 10)
        
    def start_exporter(self):
        """Start the Prometheus metrics exporter"""
        if self._running:
            return
            
        self._running = True
        
        # Start HTTP server for metrics endpoint
        self._start_metrics_server()
        
        # Start metrics update thread
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        
        self.logger.info(f"Prometheus exporter started on {self.host}:{self.port}")
        
    def stop_exporter(self):
        """Stop the Prometheus metrics exporter"""
        self._running = False
        
        if self._server:
            self._server.shutdown()
            
        if self._server_thread:
            self._server_thread.join(timeout=5)
            
        self.logger.info("Prometheus exporter stopped")
        
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metric objects"""
        
        # System metrics
        self.system_cpu_usage = Gauge(
            'edgewatch_system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'edgewatch_system_memory_usage_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk_usage = Gauge(
            'edgewatch_system_disk_usage_percent',
            'System disk usage percentage',
            registry=self.registry
        )
        
        # EdgeWatch specific metrics
        self.edge_nodes_total = Gauge(
            'edgewatch_edge_nodes_total',
            'Total number of edge nodes',
            registry=self.registry
        )
        
        self.edge_nodes_active = Gauge(
            'edgewatch_edge_nodes_active',
            'Number of active edge nodes',
            registry=self.registry
        )
        
        # Gossip protocol metrics
        self.gossip_messages_total = Counter(
            'edgewatch_gossip_messages_total',
            'Total gossip messages sent/received',
            ['direction', 'message_type', 'status'],
            registry=self.registry
        )
        
        self.gossip_latency = Histogram(
            'edgewatch_gossip_latency_seconds',
            'Gossip message latency',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'edgewatch_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'edgewatch_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry
        )
        
        # Database metrics
        self.database_connections = Gauge(
            'edgewatch_database_connections',
            'Number of database connections',
            registry=self.registry
        )
        
        self.database_operations_total = Counter(
            'edgewatch_database_operations_total',
            'Total database operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.database_operation_duration = Histogram(
            'edgewatch_database_operation_duration_seconds',
            'Database operation duration',
            ['operation'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        # Alert metrics
        self.alerts_total = Counter(
            'edgewatch_alerts_total',
            'Total alerts generated',
            ['severity', 'type', 'source'],
            registry=self.registry
        )
        
        self.alerts_active = Gauge(
            'edgewatch_alerts_active',
            'Number of active alerts',
            ['severity'],
            registry=self.registry
        )
        
        # Experiment metrics
        self.experiments_total = Counter(
            'edgewatch_experiments_total',
            'Total experiments run',
            ['type', 'status'],
            registry=self.registry
        )
        
        self.experiments_active = Gauge(
            'edgewatch_experiments_active',
            'Number of active experiments',
            registry=self.registry
        )
        
        # Performance metrics
        self.response_time_p95 = Gauge(
            'edgewatch_response_time_p95_seconds',
            '95th percentile response time',
            ['endpoint'],
            registry=self.registry
        )
        
        self.error_rate = Gauge(
            'edgewatch_error_rate',
            'Error rate percentage',
            ['endpoint'],
            registry=self.registry
        )
        
        self.throughput = Gauge(
            'edgewatch_throughput_requests_per_second',
            'Request throughput',
            ['endpoint'],
            registry=self.registry
        )
        
        # Custom application metrics
        self.edgewatch_info = Gauge(
            'edgewatch_info',
            'EdgeWatch instance information',
            ['version', 'node_id', 'environment'],
            registry=self.registry
        )
        
    def _start_metrics_server(self):
        """Start HTTP server for Prometheus metrics endpoint"""
        try:
            handler = MetricsHandler.factory(self.registry)
            self._server = HTTPServer((self.host, self.port), handler)
            
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True
            )
            self._server_thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
            raise
            
    def _update_loop(self):
        """Main loop to update Prometheus metrics"""
        while self._running:
            try:
                self._update_metrics()
                time.sleep(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error updating Prometheus metrics: {e}")
                time.sleep(self.update_interval)
                
    def _update_metrics(self):
        """Update Prometheus metrics from EdgeWatch metrics collector"""
        
        # Get latest metrics from collector
        latest_metrics = self.metrics_collector.get_aggregated_metrics('5m')
        
        # Update system metrics
        if 'cpu_usage' in latest_metrics:
            self.system_cpu_usage.set(latest_metrics['cpu_usage']['latest'] or 0)
            
        if 'memory_usage' in latest_metrics:
            self.system_memory_usage.set(latest_metrics['memory_usage']['latest'] or 0)
            
        if 'disk_usage' in latest_metrics:
            self.system_disk_usage.set(latest_metrics['disk_usage']['latest'] or 0)
            
        # Update edge node metrics
        if 'edge_node_count' in latest_metrics:
            self.edge_nodes_total.set(latest_metrics['edge_node_count']['latest'] or 0)
            
        # Update EdgeWatch info
        self.edgewatch_info.labels(
            version=self.config.get('version', '1.0.0'),
            node_id=self.config.get('node.id', 'unknown'),
            environment=self.config.get('environment', 'production')
        ).set(1)
        
    def record_api_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record API request metrics"""
        self.api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
    def record_gossip_message(self, direction: str, message_type: str, 
                            success: bool, latency: Optional[float] = None):
        """Record gossip protocol metrics"""
        status = 'success' if success else 'error'
        
        self.gossip_messages_total.labels(
            direction=direction,
            message_type=message_type,
            status=status
        ).inc()
        
        if latency is not None:
            self.gossip_latency.observe(latency)
            
    def record_database_operation(self, operation: str, success: bool, duration: float):
        """Record database operation metrics"""
        status = 'success' if success else 'error'
        
        self.database_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.database_operation_duration.labels(
            operation=operation
        ).observe(duration)
        
    def record_alert(self, severity: str, alert_type: str, source: str):
        """Record alert metrics"""
        self.alerts_total.labels(
            severity=severity,
            type=alert_type,
            source=source
        ).inc()
        
    def update_active_alerts(self, alerts_by_severity: Dict[str, int]):
        """Update active alert counts"""
        for severity, count in alerts_by_severity.items():
            self.alerts_active.labels(severity=severity).set(count)
            
    def record_experiment(self, experiment_type: str, status: str):
        """Record experiment metrics"""
        self.experiments_total.labels(
            type=experiment_type,
            status=status
        ).inc()
        
    def update_active_experiments(self, count: int):
        """Update active experiment count"""
        self.experiments_active.set(count)
        
    def update_performance_metrics(self, endpoint: str, p95_response_time: float,
                                 error_rate: float, throughput: float):
        """Update performance metrics"""
        self.response_time_p95.labels(endpoint=endpoint).set(p95_response_time)
        self.error_rate.labels(endpoint=endpoint).set(error_rate)
        self.throughput.labels(endpoint=endpoint).set(throughput)
        
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format"""
        return generate_latest(self.registry).decode('utf-8')
        
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary"""
        metrics = {}
        
        # This would parse the Prometheus metrics into a dictionary format
        # For now, return basic info
        metrics['timestamp'] = datetime.utcnow().isoformat()
        metrics['exporter_status'] = 'running' if self._running else 'stopped'
        metrics['port'] = self.port
        
        return metrics
