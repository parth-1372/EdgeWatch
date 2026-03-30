"""
Configuration for VoI-based Emulsion Experiments
"""

from typing import Dict, Any
from .voi_metrics import MetricPriority


class VoIConfig:
    """Configuration for Value of Information experiments"""
    
    # Metric priorities
    METRIC_PRIORITIES: Dict[str, MetricPriority] = {
        # System metrics
        "cpu_percent": MetricPriority.HIGH,
        "memory_percent": MetricPriority.MEDIUM,
        "disk_usage": MetricPriority.LOW,
        "network_io": MetricPriority.MEDIUM,
        "network_bytes_sent": MetricPriority.MEDIUM,
        "network_bytes_recv": MetricPriority.MEDIUM,
        
        # Container metrics
        "container_count": MetricPriority.LOW,
        "container_cpu": MetricPriority.HIGH,
        "container_memory": MetricPriority.MEDIUM,
        
        # Application metrics
        "request_rate": MetricPriority.HIGH,
        "error_rate": MetricPriority.HIGH,
        "response_time": MetricPriority.MEDIUM,
        "active_connections": MetricPriority.MEDIUM,
        
        # Edge-specific metrics
        "edge_latency": MetricPriority.HIGH,
        "cache_hit_rate": MetricPriority.MEDIUM,
        "queue_length": MetricPriority.HIGH,
    }
    
    # Delta thresholds (minimum % change to trigger update)
    METRIC_DELTAS: Dict[str, float] = {
        # System metrics
        "cpu_percent": 5.0,       # 5% change in CPU
        "memory_percent": 7.0,    # 7% change in memory
        "disk_usage": 10.0,       # 10% change in disk
        "network_io": 15.0,       # 15% change in network I/O
        "network_bytes_sent": 20.0,
        "network_bytes_recv": 20.0,
        
        # Container metrics
        "container_count": 1,     # Any change in container count
        "container_cpu": 5.0,
        "container_memory": 7.0,
        
        # Application metrics
        "request_rate": 10.0,     # 10% change in requests
        "error_rate": 0.5,        # Very sensitive to errors
        "response_time": 15.0,    # 15% change in response time
        "active_connections": 10.0,
        
        # Edge-specific metrics
        "edge_latency": 10.0,     # 10% change in latency
        "cache_hit_rate": 5.0,    # 5% change in cache hits
        "queue_length": 1,        # Any change in queue
    }
    
    # Experiment settings
    GOSSIP_RATE: float = 2.0          # seconds between gossip rounds
    TARGET_NODES: int = 3             # number of nodes to gossip with
    MAX_ROUNDS: int = 100             # maximum experiment rounds
    
    # Data collection settings
    COLLECT_METRICS_INTERVAL: int = 1  # collect metrics every N rounds
    PUSH_TO_DB_INTERVAL: int = 10      # push to database every N rounds
    
    # Bandwidth optimization
    ENABLE_VOI_FILTERING: bool = True  # Enable VoI-based filtering
    ENABLE_COMPRESSION: bool = False    # Enable data compression
    
    @classmethod
    def get_priority(cls, metric_name: str) -> MetricPriority:
        """Get priority for a metric, default to HIGH if unknown"""
        return cls.METRIC_PRIORITIES.get(metric_name, MetricPriority.HIGH)
    
    @classmethod
    def get_delta_threshold(cls, metric_name: str) -> float:
        """Get delta threshold for a metric, default to 0 if unknown"""
        return cls.METRIC_DELTAS.get(metric_name, 0.0)
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return {
            "gossip_rate": cls.GOSSIP_RATE,
            "target_nodes": cls.TARGET_NODES,
            "max_rounds": cls.MAX_ROUNDS,
            "collect_interval": cls.COLLECT_METRICS_INTERVAL,
            "push_interval": cls.PUSH_TO_DB_INTERVAL,
            "voi_enabled": cls.ENABLE_VOI_FILTERING,
            "compression_enabled": cls.ENABLE_COMPRESSION,
            "metric_priorities": {k: v.name for k, v in cls.METRIC_PRIORITIES.items()},
            "metric_deltas": cls.METRIC_DELTAS,
        }
