"""
EdgeWatch Metrics Collector
Comprehensive metrics collection for edge computing environments
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psutil
import json
import logging
from collections import defaultdict, deque

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager


class MetricsCollector:
    """Advanced metrics collection and aggregation system"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self._metrics_buffer = defaultdict(deque)
        self._aggregated_metrics = {}
        self._collection_thread = None
        self._running = False
        
        # Collection intervals (seconds)
        self.collection_interval = self.config.get('monitoring.collection_interval', 5)
        self.aggregation_interval = self.config.get('monitoring.aggregation_interval', 60)
        self.retention_period = self.config.get('monitoring.retention_hours', 24) * 3600
        
        # Metrics configuration
        self.enabled_metrics = set(self.config.get('monitoring.enabled_metrics', [
            'cpu_usage', 'memory_usage', 'disk_usage', 'network_io',
            'edge_node_count', 'gossip_messages', 'api_requests'
        ]))
        
        self._last_network_stats = None
        self._request_counts = defaultdict(int)
        
    def start_collection(self):
        """Start the metrics collection process"""
        if self._running:
            return
            
        self._running = True
        self._collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collection_thread.start()
        self.logger.info("Metrics collection started")
        
    def stop_collection(self):
        """Stop the metrics collection process"""
        self._running = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        self.logger.info("Metrics collection stopped")
        
    def record_metric(self, metric_name: str, value: Any, timestamp: Optional[datetime] = None, tags: Optional[Dict] = None):
        """Record a custom metric"""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        metric_entry = {
            'value': value,
            'timestamp': timestamp,
            'tags': tags or {}
        }
        
        self._metrics_buffer[metric_name].append(metric_entry)
        
        # Limit buffer size to prevent memory issues
        max_buffer_size = 1000
        if len(self._metrics_buffer[metric_name]) > max_buffer_size:
            self._metrics_buffer[metric_name].popleft()
            
    def get_metrics(self, metric_names: Optional[List[str]] = None, 
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> Dict[str, List]:
        """Retrieve metrics data"""
        if metric_names is None:
            metric_names = list(self._metrics_buffer.keys())
            
        result = {}
        for metric_name in metric_names:
            if metric_name not in self._metrics_buffer:
                continue
                
            metrics = list(self._metrics_buffer[metric_name])
            
            # Filter by time range if specified
            if start_time or end_time:
                filtered_metrics = []
                for metric in metrics:
                    timestamp = metric['timestamp']
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue
                    filtered_metrics.append(metric)
                metrics = filtered_metrics
                
            result[metric_name] = metrics
            
        return result
        
    def get_aggregated_metrics(self, time_window: str = '1h') -> Dict[str, Dict]:
        """Get aggregated metrics for a time window"""
        window_seconds = self._parse_time_window(time_window)
        cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        aggregated = {}
        for metric_name, metrics in self._metrics_buffer.items():
            recent_metrics = [
                m for m in metrics 
                if m['timestamp'] >= cutoff_time
            ]
            
            if not recent_metrics:
                continue
                
            values = [m['value'] for m in recent_metrics if isinstance(m['value'], (int, float))]
            if values:
                aggregated[metric_name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'latest': recent_metrics[-1]['value'] if recent_metrics else None,
                    'timestamp': datetime.utcnow()
                }
                
        return aggregated
        
    def _collection_loop(self):
        """Main collection loop"""
        last_aggregation = time.time()
        
        while self._running:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                
                # Aggregate metrics periodically
                current_time = time.time()
                if current_time - last_aggregation >= self.aggregation_interval:
                    self._aggregate_metrics()
                    self._cleanup_old_metrics()
                    last_aggregation = current_time
                    
                time.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                time.sleep(self.collection_interval)
                
    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        timestamp = datetime.utcnow()
        
        # CPU metrics
        if 'cpu_usage' in self.enabled_metrics:
            cpu_percent = psutil.cpu_percent(interval=None)
            self.record_metric('cpu_usage', cpu_percent, timestamp)
            
        # Memory metrics
        if 'memory_usage' in self.enabled_metrics:
            memory = psutil.virtual_memory()
            self.record_metric('memory_usage', memory.percent, timestamp)
            self.record_metric('memory_available', memory.available, timestamp)
            
        # Disk metrics
        if 'disk_usage' in self.enabled_metrics:
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric('disk_usage', disk_percent, timestamp)
            
        # Network metrics
        if 'network_io' in self.enabled_metrics:
            self._collect_network_metrics(timestamp)
            
    def _collect_network_metrics(self, timestamp: datetime):
        """Collect network I/O metrics"""
        try:
            net_io = psutil.net_io_counters()
            
            if self._last_network_stats:
                bytes_sent = net_io.bytes_sent - self._last_network_stats.bytes_sent
                bytes_recv = net_io.bytes_recv - self._last_network_stats.bytes_recv
                
                self.record_metric('network_bytes_sent', bytes_sent, timestamp)
                self.record_metric('network_bytes_recv', bytes_recv, timestamp)
                
            self._last_network_stats = net_io
            
        except Exception as e:
            self.logger.warning(f"Could not collect network metrics: {e}")
            
    def _aggregate_metrics(self):
        """Aggregate metrics and store in database"""
        try:
            aggregated = self.get_aggregated_metrics('1h')
            
            # Store aggregated metrics in database
            for metric_name, stats in aggregated.items():
                self.db.store_metric_aggregate(
                    metric_name=metric_name,
                    timestamp=stats['timestamp'],
                    count=stats['count'],
                    min_value=stats['min'],
                    max_value=stats['max'],
                    avg_value=stats['avg'],
                    latest_value=stats['latest']
                )
                
            self._aggregated_metrics = aggregated
            
        except Exception as e:
            self.logger.error(f"Error aggregating metrics: {e}")
            
    def _cleanup_old_metrics(self):
        """Remove old metrics from buffer"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.retention_period)
        
        for metric_name in list(self._metrics_buffer.keys()):
            metrics = self._metrics_buffer[metric_name]
            # Remove old metrics
            while metrics and metrics[0]['timestamp'] < cutoff_time:
                metrics.popleft()
                
    def _parse_time_window(self, window: str) -> int:
        """Parse time window string to seconds"""
        if window.endswith('s'):
            return int(window[:-1])
        elif window.endswith('m'):
            return int(window[:-1]) * 60
        elif window.endswith('h'):
            return int(window[:-1]) * 3600
        elif window.endswith('d'):
            return int(window[:-1]) * 86400
        else:
            return int(window)
            
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record API request metrics"""
        timestamp = datetime.utcnow()
        tags = {
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code
        }
        
        self.record_metric('api_request_duration', duration, timestamp, tags)
        self.record_metric('api_request_count', 1, timestamp, tags)
        
        # Track request counts
        key = f"{method}:{endpoint}:{status_code}"
        self._request_counts[key] += 1
        
    def record_gossip_message(self, message_type: str, node_id: str, success: bool):
        """Record gossip protocol metrics"""
        timestamp = datetime.utcnow()
        tags = {
            'message_type': message_type,
            'node_id': node_id,
            'success': success
        }
        
        self.record_metric('gossip_message', 1, timestamp, tags)
        
    def record_edge_node_event(self, event_type: str, node_id: str, node_count: int):
        """Record edge node events"""
        timestamp = datetime.utcnow()
        tags = {
            'event_type': event_type,
            'node_id': node_id
        }
        
        self.record_metric('edge_node_event', 1, timestamp, tags)
        self.record_metric('edge_node_count', node_count, timestamp)
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        latest_metrics = self.get_aggregated_metrics('5m')
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow(),
            'checks': {}
        }
        
        # Check CPU usage
        if 'cpu_usage' in latest_metrics:
            cpu_avg = latest_metrics['cpu_usage']['avg']
            if cpu_avg > 90:
                health_status['status'] = 'critical'
                health_status['checks']['cpu'] = 'critical'
            elif cpu_avg > 75:
                health_status['status'] = 'warning'
                health_status['checks']['cpu'] = 'warning'
            else:
                health_status['checks']['cpu'] = 'healthy'
                
        # Check memory usage
        if 'memory_usage' in latest_metrics:
            memory_avg = latest_metrics['memory_usage']['avg']
            if memory_avg > 95:
                health_status['status'] = 'critical'
                health_status['checks']['memory'] = 'critical'
            elif memory_avg > 85:
                health_status['status'] = 'warning'
                health_status['checks']['memory'] = 'warning'
            else:
                health_status['checks']['memory'] = 'healthy'
                
        # Check disk usage
        if 'disk_usage' in latest_metrics:
            disk_avg = latest_metrics['disk_usage']['avg']
            if disk_avg > 95:
                health_status['status'] = 'critical'
                health_status['checks']['disk'] = 'critical'
            elif disk_avg > 85:
                health_status['status'] = 'warning'
                health_status['checks']['disk'] = 'warning'
            else:
                health_status['checks']['disk'] = 'healthy'
                
        return health_status
