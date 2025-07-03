"""
EdgeWatch Performance Monitor
Real-time performance monitoring for edge computing environments
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import statistics
import logging
from collections import defaultdict, deque

from ..core.config_manager import ConfigManager
from .metrics_collector import MetricsCollector


class PerformanceMonitor:
    """Real-time performance monitoring and analysis"""
    
    def __init__(self, config_manager: ConfigManager, metrics_collector: MetricsCollector):
        self.config = config_manager
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self._response_times = defaultdict(deque)
        self._throughput_data = defaultdict(deque)
        self._error_rates = defaultdict(deque)
        self._active_requests = defaultdict(int)
        
        # Configuration
        self.window_size = self.config.get('performance.window_size', 100)
        self.alert_thresholds = {
            'response_time': self.config.get('performance.response_time_threshold', 2.0),
            'error_rate': self.config.get('performance.error_rate_threshold', 0.05),
            'throughput': self.config.get('performance.throughput_threshold', 100)
        }
        
        # Callbacks for alerts
        self._alert_callbacks = []
        
    def start_request_tracking(self, request_id: str, endpoint: str, method: str) -> dict:
        """Start tracking a request"""
        start_time = time.time()
        request_context = {
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
            'start_time': start_time,
            'timestamp': datetime.utcnow()
        }
        
        # Increment active request counter
        key = f"{method}:{endpoint}"
        self._active_requests[key] += 1
        
        return request_context
        
    def end_request_tracking(self, request_context: dict, status_code: int, 
                           bytes_sent: Optional[int] = None):
        """End tracking a request and record metrics"""
        end_time = time.time()
        duration = end_time - request_context['start_time']
        
        endpoint = request_context['endpoint']
        method = request_context['method']
        key = f"{method}:{endpoint}"
        
        # Record response time
        self._response_times[key].append(duration)
        if len(self._response_times[key]) > self.window_size:
            self._response_times[key].popleft()
            
        # Record throughput data
        throughput_entry = {
            'timestamp': datetime.utcnow(),
            'duration': duration,
            'status_code': status_code,
            'bytes_sent': bytes_sent or 0
        }
        self._throughput_data[key].append(throughput_entry)
        if len(self._throughput_data[key]) > self.window_size:
            self._throughput_data[key].popleft()
            
        # Record error rate
        is_error = status_code >= 400
        self._error_rates[key].append(is_error)
        if len(self._error_rates[key]) > self.window_size:
            self._error_rates[key].popleft()
            
        # Decrement active request counter
        self._active_requests[key] = max(0, self._active_requests[key] - 1)
        
        # Record in metrics collector
        self.metrics.record_api_request(endpoint, method, status_code, duration)
        
        # Check for performance alerts
        self._check_performance_alerts(key)
        
    def get_performance_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Get current performance statistics"""
        stats = {}
        
        keys_to_check = []
        if endpoint:
            # Find keys that match the endpoint
            keys_to_check = [k for k in self._response_times.keys() if endpoint in k]
        else:
            keys_to_check = list(self._response_times.keys())
            
        for key in keys_to_check:
            response_times = list(self._response_times[key])
            error_rates = list(self._error_rates[key])
            throughput_data = list(self._throughput_data[key])
            
            if response_times:
                stats[key] = {
                    'response_time': {
                        'avg': statistics.mean(response_times),
                        'median': statistics.median(response_times),
                        'p95': self._percentile(response_times, 95),
                        'p99': self._percentile(response_times, 99),
                        'min': min(response_times),
                        'max': max(response_times)
                    },
                    'error_rate': sum(error_rates) / len(error_rates) if error_rates else 0,
                    'throughput': {
                        'requests_per_second': self._calculate_rps(throughput_data),
                        'active_requests': self._active_requests[key]
                    },
                    'total_requests': len(response_times)
                }
                
        return stats
        
    def get_system_performance(self) -> Dict[str, Any]:
        """Get overall system performance metrics"""
        all_response_times = []
        all_error_rates = []
        all_throughput = []
        
        for key in self._response_times:
            all_response_times.extend(list(self._response_times[key]))
            all_error_rates.extend(list(self._error_rates[key]))
            all_throughput.extend(list(self._throughput_data[key]))
            
        system_stats = {
            'overall_health': 'healthy',
            'timestamp': datetime.utcnow()
        }
        
        if all_response_times:
            avg_response_time = statistics.mean(all_response_times)
            system_stats['response_time'] = {
                'avg': avg_response_time,
                'p95': self._percentile(all_response_times, 95),
                'p99': self._percentile(all_response_times, 99)
            }
            
            # Check health based on response time
            if avg_response_time > self.alert_thresholds['response_time'] * 2:
                system_stats['overall_health'] = 'critical'
            elif avg_response_time > self.alert_thresholds['response_time']:
                system_stats['overall_health'] = 'warning'
                
        if all_error_rates:
            error_rate = sum(all_error_rates) / len(all_error_rates)
            system_stats['error_rate'] = error_rate
            
            # Check health based on error rate
            if error_rate > self.alert_thresholds['error_rate'] * 2:
                system_stats['overall_health'] = 'critical'
            elif error_rate > self.alert_thresholds['error_rate']:
                system_stats['overall_health'] = 'warning'
                
        if all_throughput:
            system_stats['throughput'] = {
                'total_rps': self._calculate_rps(all_throughput),
                'total_active_requests': sum(self._active_requests.values())
            }
            
        return system_stats
        
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Add a callback function for performance alerts"""
        self._alert_callbacks.append(callback)
        
    def _check_performance_alerts(self, key: str):
        """Check if performance metrics exceed thresholds"""
        response_times = list(self._response_times[key])
        error_rates = list(self._error_rates[key])
        
        alerts = []
        
        # Check response time
        if len(response_times) >= 10:  # Need sufficient data
            avg_response_time = statistics.mean(response_times[-10:])  # Last 10 requests
            if avg_response_time > self.alert_thresholds['response_time']:
                alerts.append({
                    'type': 'response_time',
                    'threshold': self.alert_thresholds['response_time'],
                    'actual': avg_response_time,
                    'severity': 'critical' if avg_response_time > self.alert_thresholds['response_time'] * 2 else 'warning'
                })
                
        # Check error rate
        if len(error_rates) >= 10:  # Need sufficient data
            recent_error_rate = sum(error_rates[-10:]) / 10  # Last 10 requests
            if recent_error_rate > self.alert_thresholds['error_rate']:
                alerts.append({
                    'type': 'error_rate',
                    'threshold': self.alert_thresholds['error_rate'],
                    'actual': recent_error_rate,
                    'severity': 'critical' if recent_error_rate > self.alert_thresholds['error_rate'] * 2 else 'warning'
                })
                
        # Send alerts
        for alert in alerts:
            alert_data = {
                'endpoint': key,
                'alert': alert,
                'timestamp': datetime.utcnow()
            }
            
            self.logger.warning(f"Performance alert for {key}: {alert['type']} = {alert['actual']}")
            
            for callback in self._alert_callbacks:
                try:
                    callback(key, alert_data)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
                    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a dataset"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        weight = index - lower_index
        return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
        
    def _calculate_rps(self, throughput_data: List[Dict]) -> float:
        """Calculate requests per second"""
        if len(throughput_data) < 2:
            return 0.0
            
        # Calculate RPS over the last minute
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        recent_requests = [
            req for req in throughput_data 
            if req['timestamp'] >= one_minute_ago
        ]
        
        if len(recent_requests) < 2:
            return len(recent_requests)  # Less than 1 minute of data
            
        time_span = (recent_requests[-1]['timestamp'] - recent_requests[0]['timestamp']).total_seconds()
        if time_span > 0:
            return len(recent_requests) / time_span
        return 0.0
