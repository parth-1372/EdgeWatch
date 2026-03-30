"""
VoI-based Metric Filtering
Implements priority-based and delta-based metric filtering
to reduce bandwidth usage while maintaining monitoring accuracy
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import time

logger = logging.getLogger("edgewatch.voi_metrics")


class MetricPriority(Enum):
    """Priority levels for different metrics"""
    HIGH = 1      # Update every round - critical metrics
    MEDIUM = 5    # Update every 5 rounds - important but not critical
    LOW = 10      # Update every 10 rounds - slowly changing metrics


class VoIConfig:
    """Configuration for VoI-based metric filtering"""
    
    # Default priority assignments
    DEFAULT_PRIORITIES = {
        "cpu_percent": MetricPriority.HIGH,
        "memory_percent": MetricPriority.MEDIUM,
        "disk_usage": MetricPriority.LOW,
        "network_io": MetricPriority.MEDIUM,
        "container_count": MetricPriority.LOW,
        "request_rate": MetricPriority.HIGH,
        "error_rate": MetricPriority.HIGH,
        "response_time": MetricPriority.MEDIUM,
    }
    
    # Delta thresholds (minimum % change to trigger update)
    DEFAULT_DELTAS = {
        "cpu_percent": 5.0,       # 5% change
        "memory_percent": 7.0,    # 7% change
        "disk_usage": 10.0,       # 10% change
        "network_io": 15.0,       # 15% change
        "container_count": 1,     # Any change
        "request_rate": 10.0,     # 10% change
        "error_rate": 0.1,        # 0.1% change (very sensitive)
        "response_time": 20.0,    # 20% change
    }


class VoIMetricFilter:
    """
    Implements Value of Information based metric filtering
    Decides which metrics to send based on:
    1. Priority level
    2. Delta threshold
    3. Time since last sent
    """
    
    def __init__(self, 
                 priorities: Optional[Dict[str, MetricPriority]] = None,
                 deltas: Optional[Dict[str, float]] = None):
        """
        Initialize VoI filter
        
        Args:
            priorities: Custom priority mapping for metrics
            deltas: Custom delta thresholds for metrics
        """
        self.priorities = priorities or VoIConfig.DEFAULT_PRIORITIES
        self.deltas = deltas or VoIConfig.DEFAULT_DELTAS
        
        # Track last values and send times
        self.last_metric_values: Dict[str, Any] = {}
        self.last_metric_sent_round: Dict[str, int] = {}
        self.current_round = 0
        
        # Statistics tracking
        self.stats = {
            "total_metrics_evaluated": 0,
            "metrics_sent": 0,
            "metrics_filtered": 0,
            "bandwidth_saved_percent": 0.0
        }
        
        logger.info("VoI Metric Filter initialized")
    
    def should_send_metric(self, 
                          metric_name: str, 
                          value: Any,
                          force: bool = False) -> Tuple[bool, str]:
        """
        Determine if a metric should be sent
        
        Args:
            metric_name: Name of the metric
            value: Current value of the metric
            force: Force send regardless of rules
            
        Returns:
            Tuple of (should_send, reason)
        """
        self.stats["total_metrics_evaluated"] += 1
        
        # Force send if requested
        if force:
            self._update_tracking(metric_name, value, sent=True)
            self.stats["metrics_sent"] += 1
            return True, "FORCED"
        
        # First time seeing this metric - always send
        if metric_name not in self.last_metric_values:
            self._update_tracking(metric_name, value, sent=True)
            self.stats["metrics_sent"] += 1
            return True, "FIRST_TIME"
        
        # Get priority for this metric (default to HIGH if unknown)
        priority = self.priorities.get(metric_name, MetricPriority.HIGH)
        
        # Calculate rounds since last sent
        rounds_since_sent = self.current_round - self.last_metric_sent_round.get(metric_name, 0)
        
        # Calculate delta (percent change)
        delta_percent = self._calculate_delta(metric_name, value)
        
        # Decision logic
        should_send = False
        reason = ""
        
        # Always send high priority metrics
        if priority == MetricPriority.HIGH:
            should_send = True
            reason = "HIGH_PRIORITY"
        # Send if enough rounds have passed based on priority
        elif rounds_since_sent >= priority.value:
            should_send = True
            reason = f"SCHEDULE_{priority.name}"
        # Send if significant change detected
        elif delta_percent is not None and delta_percent >= self.deltas.get(metric_name, 0):
            should_send = True
            reason = f"DELTA_{delta_percent:.2f}%"
        else:
            reason = f"FILTERED_rounds={rounds_since_sent}_delta={delta_percent}"
        
        # Update tracking
        self._update_tracking(metric_name, value, sent=should_send)
        
        # Update stats
        if should_send:
            self.stats["metrics_sent"] += 1
        else:
            self.stats["metrics_filtered"] += 1
        
        # Log decision
        logger.debug(
            f"VoI Decision: metric={metric_name}, value={value}, "
            f"priority={priority.name}, delta={delta_percent}, "
            f"rounds_since_sent={rounds_since_sent}, "
            f"decision={'SEND' if should_send else 'SKIP'}, reason={reason}"
        )
        
        return should_send, reason
    
    def _calculate_delta(self, metric_name: str, current_value: Any) -> Optional[float]:
        """Calculate percentage change from last value"""
        last_value = self.last_metric_values.get(metric_name)
        
        # Can't calculate delta without previous value
        if last_value is None:
            return None
        
        # Only calculate for numeric values
        if not isinstance(current_value, (int, float)) or not isinstance(last_value, (int, float)):
            # For non-numeric, treat any change as 100%
            return 100.0 if current_value != last_value else 0.0
        
        # Avoid division by zero
        if last_value == 0:
            return 100.0 if current_value != 0 else 0.0
        
        # Calculate percentage change
        delta = abs((current_value - last_value) / last_value) * 100
        return delta
    
    def _update_tracking(self, metric_name: str, value: Any, sent: bool):
        """Update tracking dictionaries"""
        # Always update last value
        self.last_metric_values[metric_name] = value
        
        # Update last sent round if sent
        if sent:
            self.last_metric_sent_round[metric_name] = self.current_round
    
    def filter_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a dictionary of metrics
        
        Args:
            metrics: Dictionary of metric_name -> value
            
        Returns:
            Filtered dictionary with only metrics that should be sent
        """
        filtered = {}
        metadata = {
            "round": self.current_round,
            "filter_decisions": {}
        }
        
        for metric_name, value in metrics.items():
            should_send, reason = self.should_send_metric(metric_name, value)
            metadata["filter_decisions"][metric_name] = {
                "sent": should_send,
                "reason": reason,
                "value": value
            }
            
            if should_send:
                filtered[metric_name] = value
        
        return filtered, metadata
    
    def advance_round(self):
        """Advance to next round (call this at each gossip cycle)"""
        self.current_round += 1
        logger.debug(f"Advanced to round {self.current_round}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current filtering statistics"""
        total = self.stats["total_metrics_evaluated"]
        if total > 0:
            self.stats["bandwidth_saved_percent"] = (
                self.stats["metrics_filtered"] / total * 100
            )
        
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            "total_metrics_evaluated": 0,
            "metrics_sent": 0,
            "metrics_filtered": 0,
            "bandwidth_saved_percent": 0.0
        }
        logger.info("Statistics reset")
