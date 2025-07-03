"""
EdgeWatch Resource Tracker
Detailed resource utilization tracking and analysis
"""

import threading
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from collections import defaultdict, deque

from ..core.config_manager import ConfigManager
from .metrics_collector import MetricsCollector


class ResourceTracker:
    """Comprehensive resource utilization tracking"""
    
    def __init__(self, config_manager: ConfigManager, metrics_collector: MetricsCollector):
        self.config = config_manager
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Resource tracking data
        self._cpu_history = deque(maxlen=1000)
        self._memory_history = deque(maxlen=1000)
        self._disk_history = deque(maxlen=1000)
        self._network_history = deque(maxlen=1000)
        self._process_history = defaultdict(lambda: deque(maxlen=100))
        
        # Configuration
        self.track_processes = self.config.get('monitoring.track_processes', True)
        self.process_threshold_cpu = self.config.get('monitoring.process_cpu_threshold', 5.0)
        self.process_threshold_memory = self.config.get('monitoring.process_memory_threshold', 100)  # MB
        
        # Tracking state
        self._running = False
        self._tracking_thread = None
        self._last_network_counters = None
        
    def start_tracking(self):
        """Start resource tracking"""
        if self._running:
            return
            
        self._running = True
        self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._tracking_thread.start()
        self.logger.info("Resource tracking started")
        
    def stop_tracking(self):
        """Stop resource tracking"""
        self._running = False
        if self._tracking_thread:
            self._tracking_thread.join(timeout=5)
        self.logger.info("Resource tracking stopped")
        
    def get_current_resources(self) -> Dict[str, Any]:
        """Get current resource utilization"""
        timestamp = datetime.utcnow()
        
        # CPU information
        cpu_info = {
            'usage_percent': psutil.cpu_percent(interval=None),
            'count': psutil.cpu_count(),
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None,
            'per_cpu': psutil.cpu_percent(interval=None, percpu=True)
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        memory_info = {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'usage_percent': memory.percent,
            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_percent': swap.percent
        }
        
        # Disk information
        disk_info = {}
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info[partition.device] = {
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'usage_percent': (usage.used / usage.total) * 100 if usage.total > 0 else 0
                }
            except PermissionError:
                continue
                
        # Network information
        network_info = {}
        try:
            net_io = psutil.net_io_counters(pernic=True)
            for interface, stats in net_io.items():
                network_info[interface] = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv,
                    'errors_in': stats.errin,
                    'errors_out': stats.errout,
                    'drops_in': stats.dropin,
                    'drops_out': stats.dropout
                }
        except Exception as e:
            self.logger.warning(f"Could not get network info: {e}")
            
        return {
            'timestamp': timestamp,
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'network': network_info
        }
        
    def get_process_resources(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get resource usage for top processes"""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'create_time']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] is not None and proc_info['memory_info'] is not None:
                        memory_mb = proc_info['memory_info'].rss / 1024 / 1024
                        
                        # Only track processes above threshold
                        if (proc_info['cpu_percent'] >= self.process_threshold_cpu or 
                            memory_mb >= self.process_threshold_memory):
                            
                            processes.append({
                                'pid': proc_info['pid'],
                                'name': proc_info['name'],
                                'cpu_percent': proc_info['cpu_percent'],
                                'memory_mb': memory_mb,
                                'create_time': datetime.fromtimestamp(proc_info['create_time'])
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error getting process resources: {e}")
            
        # Sort by CPU usage and limit results
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return processes[:limit]
        
    def get_resource_history(self, resource_type: str, 
                           start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> List[Dict]:
        """Get historical resource data"""
        history_map = {
            'cpu': self._cpu_history,
            'memory': self._memory_history,
            'disk': self._disk_history,
            'network': self._network_history
        }
        
        if resource_type not in history_map:
            return []
            
        history = list(history_map[resource_type])
        
        # Filter by time range
        if start_time or end_time:
            filtered_history = []
            for entry in history:
                timestamp = entry['timestamp']
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                filtered_history.append(entry)
            history = filtered_history
            
        return history
        
    def get_resource_trends(self, time_window: str = '1h') -> Dict[str, Any]:
        """Analyze resource trends over time window"""
        window_seconds = self._parse_time_window(time_window)
        cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        trends = {}
        
        # Analyze CPU trends
        cpu_data = [
            entry['cpu_usage'] for entry in self._cpu_history
            if entry['timestamp'] >= cutoff_time
        ]
        if cpu_data:
            trends['cpu'] = self._calculate_trend_stats(cpu_data)
            
        # Analyze memory trends
        memory_data = [
            entry['memory_usage'] for entry in self._memory_history
            if entry['timestamp'] >= cutoff_time
        ]
        if memory_data:
            trends['memory'] = self._calculate_trend_stats(memory_data)
            
        # Analyze disk trends
        disk_data = [
            entry['disk_usage'] for entry in self._disk_history
            if entry['timestamp'] >= cutoff_time
        ]
        if disk_data:
            trends['disk'] = self._calculate_trend_stats(disk_data)
            
        return trends
        
    def get_resource_alerts(self) -> List[Dict[str, Any]]:
        """Check for resource-based alerts"""
        alerts = []
        current_resources = self.get_current_resources()
        
        # CPU alerts
        cpu_usage = current_resources['cpu']['usage_percent']
        if cpu_usage > 90:
            alerts.append({
                'type': 'cpu_high',
                'severity': 'critical',
                'message': f"CPU usage at {cpu_usage:.1f}%",
                'value': cpu_usage,
                'threshold': 90
            })
        elif cpu_usage > 80:
            alerts.append({
                'type': 'cpu_high',
                'severity': 'warning',
                'message': f"CPU usage at {cpu_usage:.1f}%",
                'value': cpu_usage,
                'threshold': 80
            })
            
        # Memory alerts
        memory_usage = current_resources['memory']['usage_percent']
        if memory_usage > 95:
            alerts.append({
                'type': 'memory_high',
                'severity': 'critical',
                'message': f"Memory usage at {memory_usage:.1f}%",
                'value': memory_usage,
                'threshold': 95
            })
        elif memory_usage > 85:
            alerts.append({
                'type': 'memory_high',
                'severity': 'warning',
                'message': f"Memory usage at {memory_usage:.1f}%",
                'value': memory_usage,
                'threshold': 85
            })
            
        # Disk alerts
        for device, disk_info in current_resources['disk'].items():
            disk_usage = disk_info['usage_percent']
            if disk_usage > 95:
                alerts.append({
                    'type': 'disk_high',
                    'severity': 'critical',
                    'message': f"Disk {device} usage at {disk_usage:.1f}%",
                    'value': disk_usage,
                    'threshold': 95,
                    'device': device
                })
            elif disk_usage > 85:
                alerts.append({
                    'type': 'disk_high',
                    'severity': 'warning',
                    'message': f"Disk {device} usage at {disk_usage:.1f}%",
                    'value': disk_usage,
                    'threshold': 85,
                    'device': device
                })
                
        return alerts
        
    def _tracking_loop(self):
        """Main tracking loop"""
        while self._running:
            try:
                timestamp = datetime.utcnow()
                current_resources = self.get_current_resources()
                
                # Store CPU data
                cpu_entry = {
                    'timestamp': timestamp,
                    'cpu_usage': current_resources['cpu']['usage_percent'],
                    'cpu_count': current_resources['cpu']['count'],
                    'load_average': current_resources['cpu'].get('load_average')
                }
                self._cpu_history.append(cpu_entry)
                
                # Store memory data
                memory_entry = {
                    'timestamp': timestamp,
                    'memory_usage': current_resources['memory']['usage_percent'],
                    'memory_available': current_resources['memory']['available'],
                    'swap_usage': current_resources['memory']['swap_percent']
                }
                self._memory_history.append(memory_entry)
                
                # Store disk data
                total_disk_usage = 0
                disk_count = 0
                for device, disk_info in current_resources['disk'].items():
                    total_disk_usage += disk_info['usage_percent']
                    disk_count += 1
                    
                if disk_count > 0:
                    disk_entry = {
                        'timestamp': timestamp,
                        'disk_usage': total_disk_usage / disk_count,
                        'disks': current_resources['disk']
                    }
                    self._disk_history.append(disk_entry)
                    
                # Store network data
                if self._last_network_counters:
                    network_entry = {
                        'timestamp': timestamp,
                        'interfaces': current_resources['network']
                    }
                    self._network_history.append(network_entry)
                    
                self._last_network_counters = current_resources['network']
                
                # Track processes if enabled
                if self.track_processes:
                    processes = self.get_process_resources()
                    for proc in processes:
                        proc_key = f"{proc['name']}_{proc['pid']}"
                        self._process_history[proc_key].append({
                            'timestamp': timestamp,
                            'cpu_percent': proc['cpu_percent'],
                            'memory_mb': proc['memory_mb']
                        })
                        
                # Record metrics
                self.metrics.record_metric('system_cpu_usage', current_resources['cpu']['usage_percent'], timestamp)
                self.metrics.record_metric('system_memory_usage', current_resources['memory']['usage_percent'], timestamp)
                
                time.sleep(5)  # Collect every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in resource tracking: {e}")
                time.sleep(5)
                
    def _calculate_trend_stats(self, data: List[float]) -> Dict[str, Any]:
        """Calculate trend statistics for a dataset"""
        if not data:
            return {}
            
        return {
            'min': min(data),
            'max': max(data),
            'avg': sum(data) / len(data),
            'current': data[-1] if data else 0,
            'trend': 'increasing' if len(data) > 1 and data[-1] > data[0] else 'decreasing' if len(data) > 1 and data[-1] < data[0] else 'stable',
            'samples': len(data)
        }
        
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
