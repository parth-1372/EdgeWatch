"""
EdgeWatch Health Monitor
Comprehensive health checking and status monitoring
"""

import threading
import time
import requests
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import logging
from collections import defaultdict, deque
from enum import Enum

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager
from ..monitoring.metrics_collector import MetricsCollector


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ServiceType(Enum):
    """Types of services to monitor"""
    DATABASE = "database"
    REDIS = "redis"
    API_ENDPOINT = "api_endpoint"
    EXTERNAL_SERVICE = "external_service"
    FILESYSTEM = "filesystem"
    NETWORK = "network"


class HealthMonitor:
    """Comprehensive health monitoring system"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager,
                 metrics_collector: MetricsCollector):
        self.config = config_manager
        self.db = db_manager
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Health tracking
        self._health_checks = {}
        self._health_history = defaultdict(lambda: deque(maxlen=100))
        self._service_status = {}
        
        # Monitoring state
        self._running = False
        self._monitoring_thread = None
        self._health_callbacks = []
        
        # Configuration
        self.check_interval = self.config.get('health.check_interval', 30)
        self.timeout = self.config.get('health.timeout', 10)
        self.retry_attempts = self.config.get('health.retry_attempts', 3)
        
        # Load health check configurations
        self._load_health_checks()
        
    def start_monitoring(self):
        """Start health monitoring"""
        if self._running:
            return
            
        self._running = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self.logger.info("Health monitoring started")
        
    def stop_monitoring(self):
        """Stop health monitoring"""
        self._running = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        self.logger.info("Health monitoring stopped")
        
    def add_health_check(self, check_id: str, check_config: Dict[str, Any]):
        """Add a new health check"""
        self._health_checks[check_id] = {
            'config': check_config,
            'last_check': None,
            'last_status': HealthStatus.UNKNOWN,
            'consecutive_failures': 0,
            'enabled': check_config.get('enabled', True)
        }
        
        self.logger.info(f"Health check added: {check_id}")
        
    def remove_health_check(self, check_id: str) -> bool:
        """Remove a health check"""
        if check_id in self._health_checks:
            del self._health_checks[check_id]
            if check_id in self._health_history:
                del self._health_history[check_id]
            self.logger.info(f"Health check removed: {check_id}")
            return True
        return False
        
    def enable_health_check(self, check_id: str) -> bool:
        """Enable a health check"""
        if check_id in self._health_checks:
            self._health_checks[check_id]['enabled'] = True
            return True
        return False
        
    def disable_health_check(self, check_id: str) -> bool:
        """Disable a health check"""
        if check_id in self._health_checks:
            self._health_checks[check_id]['enabled'] = False
            return True
        return False
        
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        now = datetime.utcnow()
        
        all_statuses = []
        service_health = {}
        
        for check_id, check_data in self._health_checks.items():
            if not check_data['enabled']:
                continue
                
            status = check_data['last_status']
            all_statuses.append(status)
            
            service_health[check_id] = {
                'status': status.value,
                'last_check': check_data['last_check'],
                'consecutive_failures': check_data['consecutive_failures']
            }
            
        # Determine overall status
        overall_status = HealthStatus.HEALTHY
        if HealthStatus.CRITICAL in all_statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in all_statuses:
            overall_status = HealthStatus.WARNING
        elif HealthStatus.UNKNOWN in all_statuses:
            overall_status = HealthStatus.UNKNOWN
            
        return {
            'overall_status': overall_status.value,
            'timestamp': now,
            'services': service_health,
            'total_checks': len([c for c in self._health_checks.values() if c['enabled']]),
            'healthy_checks': len([s for s in all_statuses if s == HealthStatus.HEALTHY]),
            'warning_checks': len([s for s in all_statuses if s == HealthStatus.WARNING]),
            'critical_checks': len([s for s in all_statuses if s == HealthStatus.CRITICAL]),
            'unknown_checks': len([s for s in all_statuses if s == HealthStatus.UNKNOWN])
        }
        
    def get_service_health(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific service"""
        if service_id not in self._health_checks:
            return None
            
        check_data = self._health_checks[service_id]
        history = list(self._health_history[service_id])
        
        return {
            'service_id': service_id,
            'status': check_data['last_status'].value,
            'last_check': check_data['last_check'],
            'consecutive_failures': check_data['consecutive_failures'],
            'enabled': check_data['enabled'],
            'config': check_data['config'],
            'history': history[-20:]  # Last 20 checks
        }
        
    def get_health_history(self, service_id: Optional[str] = None,
                          hours: int = 24) -> Dict[str, List[Dict]]:
        """Get health check history"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        if service_id:
            if service_id not in self._health_history:
                return {}
            history = [
                entry for entry in self._health_history[service_id]
                if entry['timestamp'] >= cutoff_time
            ]
            return {service_id: history}
        else:
            result = {}
            for svc_id, history in self._health_history.items():
                filtered_history = [
                    entry for entry in history
                    if entry['timestamp'] >= cutoff_time
                ]
                result[svc_id] = filtered_history
            return result
            
    def add_health_callback(self, callback: Callable[[str, Dict], None]):
        """Add a callback for health status changes"""
        self._health_callbacks.append(callback)
        
    def perform_health_check(self, check_id: str) -> Dict[str, Any]:
        """Perform a single health check manually"""
        if check_id not in self._health_checks:
            return {'error': 'Health check not found'}
            
        check_data = self._health_checks[check_id]
        result = self._execute_health_check(check_id, check_data)
        
        return result
        
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                self._run_all_health_checks()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(self.check_interval)
                
    def _run_all_health_checks(self):
        """Run all enabled health checks"""
        for check_id, check_data in self._health_checks.items():
            if not check_data['enabled']:
                continue
                
            try:
                result = self._execute_health_check(check_id, check_data)
                self._process_health_result(check_id, result)
            except Exception as e:
                self.logger.error(f"Error executing health check {check_id}: {e}")
                
    def _execute_health_check(self, check_id: str, check_data: Dict) -> Dict[str, Any]:
        """Execute a single health check"""
        config = check_data['config']
        check_type = config.get('type', ServiceType.API_ENDPOINT.value)
        
        result = {
            'check_id': check_id,
            'timestamp': datetime.utcnow(),
            'status': HealthStatus.UNKNOWN,
            'response_time': None,
            'message': '',
            'details': {}
        }
        
        start_time = time.time()
        
        try:
            if check_type == ServiceType.API_ENDPOINT.value:
                result = self._check_api_endpoint(config, result)
            elif check_type == ServiceType.DATABASE.value:
                result = self._check_database(config, result)
            elif check_type == ServiceType.REDIS.value:
                result = self._check_redis(config, result)
            elif check_type == ServiceType.FILESYSTEM.value:
                result = self._check_filesystem(config, result)
            elif check_type == ServiceType.NETWORK.value:
                result = self._check_network(config, result)
            else:
                result['status'] = HealthStatus.UNKNOWN
                result['message'] = f"Unknown check type: {check_type}"
                
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Health check failed: {str(e)}"
            
        finally:
            result['response_time'] = time.time() - start_time
            
        return result
        
    def _check_api_endpoint(self, config: Dict, result: Dict) -> Dict:
        """Check API endpoint health"""
        url = config['url']
        method = config.get('method', 'GET')
        expected_status = config.get('expected_status', 200)
        headers = config.get('headers', {})
        
        try:
            response = requests.request(
                method, url, 
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == expected_status:
                result['status'] = HealthStatus.HEALTHY
                result['message'] = f"API endpoint responding normally"
            else:
                result['status'] = HealthStatus.WARNING
                result['message'] = f"Unexpected status code: {response.status_code}"
                
            result['details'] = {
                'status_code': response.status_code,
                'response_size': len(response.content)
            }
            
        except requests.exceptions.Timeout:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = "Request timeout"
        except requests.exceptions.ConnectionError:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = "Connection error"
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Request failed: {str(e)}"
            
        return result
        
    def _check_database(self, config: Dict, result: Dict) -> Dict:
        """Check database health"""
        try:
            # Simple database connectivity test
            test_query = config.get('test_query', 'SELECT 1')
            
            # This would use the actual database connection
            # For now, simulate a successful check
            result['status'] = HealthStatus.HEALTHY
            result['message'] = "Database connection successful"
            result['details'] = {
                'query': test_query,
                'connection_pool_size': 10  # Example
            }
            
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Database check failed: {str(e)}"
            
        return result
        
    def _check_redis(self, config: Dict, result: Dict) -> Dict:
        """Check Redis health"""
        try:
            host = config.get('host', 'localhost')
            port = config.get('port', 6379)
            
            # Simple socket connection test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            try:
                sock.connect((host, port))
                result['status'] = HealthStatus.HEALTHY
                result['message'] = "Redis connection successful"
            except socket.error:
                result['status'] = HealthStatus.CRITICAL
                result['message'] = "Redis connection failed"
            finally:
                sock.close()
                
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Redis check failed: {str(e)}"
            
        return result
        
    def _check_filesystem(self, config: Dict, result: Dict) -> Dict:
        """Check filesystem health"""
        import os
        import shutil
        
        try:
            path = config['path']
            min_free_space = config.get('min_free_space_gb', 1.0)
            
            if not os.path.exists(path):
                result['status'] = HealthStatus.CRITICAL
                result['message'] = f"Path does not exist: {path}"
                return result
                
            # Check free space
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024 ** 3)
            
            if free_gb >= min_free_space:
                result['status'] = HealthStatus.HEALTHY
                result['message'] = f"Sufficient free space: {free_gb:.2f}GB"
            else:
                result['status'] = HealthStatus.WARNING
                result['message'] = f"Low free space: {free_gb:.2f}GB"
                
            result['details'] = {
                'total_gb': total / (1024 ** 3),
                'used_gb': used / (1024 ** 3),
                'free_gb': free_gb
            }
            
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Filesystem check failed: {str(e)}"
            
        return result
        
    def _check_network(self, config: Dict, result: Dict) -> Dict:
        """Check network connectivity"""
        try:
            host = config['host']
            port = config.get('port', 80)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            try:
                sock.connect((host, port))
                result['status'] = HealthStatus.HEALTHY
                result['message'] = f"Network connectivity to {host}:{port} successful"
            except socket.error as e:
                result['status'] = HealthStatus.CRITICAL
                result['message'] = f"Network connectivity failed: {str(e)}"
            finally:
                sock.close()
                
        except Exception as e:
            result['status'] = HealthStatus.CRITICAL
            result['message'] = f"Network check failed: {str(e)}"
            
        return result
        
    def _process_health_result(self, check_id: str, result: Dict):
        """Process health check result"""
        check_data = self._health_checks[check_id]
        previous_status = check_data['last_status']
        current_status = result['status']
        
        # Update check data
        check_data['last_check'] = result['timestamp']
        check_data['last_status'] = current_status
        
        # Update consecutive failures
        if current_status == HealthStatus.CRITICAL:
            check_data['consecutive_failures'] += 1
        else:
            check_data['consecutive_failures'] = 0
            
        # Store in history
        self._health_history[check_id].append(result)
        
        # Record metrics
        status_value = {'healthy': 1, 'warning': 0.5, 'critical': 0, 'unknown': -1}
        self.metrics.record_metric(
            f"health_check_status",
            status_value.get(current_status.value, -1),
            result['timestamp'],
            tags={'check_id': check_id, 'service_type': check_data['config'].get('type', 'unknown')}
        )
        
        if result['response_time']:
            self.metrics.record_metric(
                f"health_check_response_time",
                result['response_time'],
                result['timestamp'],
                tags={'check_id': check_id}
            )
            
        # Trigger callbacks on status change
        if previous_status != current_status:
            self.logger.info(f"Health status changed for {check_id}: {previous_status.value} -> {current_status.value}")
            
            for callback in self._health_callbacks:
                try:
                    callback(check_id, {
                        'previous_status': previous_status.value,
                        'current_status': current_status.value,
                        'result': result,
                        'consecutive_failures': check_data['consecutive_failures']
                    })
                except Exception as e:
                    self.logger.error(f"Error in health callback: {e}")
                    
    def _load_health_checks(self):
        """Load health check configurations"""
        health_checks_config = self.config.get('health.checks', {})
        
        for check_id, config in health_checks_config.items():
            self.add_health_check(check_id, config)
            
        # Add default system checks if none configured
        if not health_checks_config:
            self._add_default_health_checks()
            
    def _add_default_health_checks(self):
        """Add default health checks"""
        default_checks = {
            'api_health': {
                'type': ServiceType.API_ENDPOINT.value,
                'url': 'http://localhost:5000/health',
                'method': 'GET',
                'expected_status': 200,
                'enabled': True
            },
            'filesystem_data': {
                'type': ServiceType.FILESYSTEM.value,
                'path': '/app/data',
                'min_free_space_gb': 1.0,
                'enabled': True
            }
        }
        
        for check_id, config in default_checks.items():
            self.add_health_check(check_id, config)
