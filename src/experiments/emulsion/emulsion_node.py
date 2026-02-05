"""
Emulsion Node - Integrates VoI-based filtering with EdgeWatch
Experimental implementation for bandwidth-efficient monitoring
"""

import logging
import time
from typing import Dict, Any, List, Optional
import psutil
import json

from .voi_metrics import VoIMetricFilter
from .config import VoIConfig

logger = logging.getLogger("edgewatch.emulsion_node")


class EmulsionNode:
    """
    Experimental node implementation with VoI-based metric filtering
    Integrates with EdgeWatch's monitoring infrastructure
    """
    
    def __init__(self, node_id: str, enable_voi: bool = True):
        """
        Initialize Emulsion Node
        
        Args:
            node_id: Unique identifier for this node
            enable_voi: Enable VoI-based filtering
        """
        self.node_id = node_id
        self.enable_voi = enable_voi
        
        # Initialize VoI filter
        self.voi_filter = VoIMetricFilter(
            priorities=VoIConfig.METRIC_PRIORITIES,
            deltas=VoIConfig.METRIC_DELTAS
        ) if enable_voi else None
        
        # Node state
        self.current_cycle = 0
        self.is_alive = True
        self.node_list: List[Dict[str, str]] = []
        
        # Data storage
        self.local_metrics: Dict[int, Dict[str, Any]] = {}  # cycle -> metrics
        self.gossip_data: Dict[str, Any] = {}  # received gossip data
        
        # Statistics
        self.stats = {
            "total_rounds": 0,
            "metrics_collected": 0,
            "metrics_sent": 0,
            "metrics_filtered": 0,
            "bandwidth_saved": 0,
            "gossip_messages_sent": 0,
            "gossip_messages_received": 0,
        }
        
        logger.info(f"EmulsionNode {node_id} initialized (VoI: {enable_voi})")
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect system metrics
        
        Returns:
            Dictionary of current system metrics
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            disk_free = disk.free
            
            # Network metrics
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent
            network_bytes_recv = net_io.bytes_recv
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available": memory_available,
                "disk_usage": disk_usage,
                "disk_free": disk_free,
                "network_bytes_sent": network_bytes_sent,
                "network_bytes_recv": network_bytes_recv,
                "timestamp": time.time(),
                "cycle": self.current_cycle,
                "node_id": self.node_id,
            }
            
            self.stats["metrics_collected"] += len(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {}
    
    def filter_metrics_for_gossip(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter metrics using VoI before gossiping
        
        Args:
            metrics: Raw metrics dictionary
            
        Returns:
            Filtered metrics dictionary
        """
        if not self.enable_voi or not self.voi_filter:
            return metrics
        
        # Extract metrics that need filtering
        filterable_metrics = {
            k: v for k, v in metrics.items()
            if k not in ["timestamp", "cycle", "node_id"]
        }
        
        # Apply VoI filtering
        filtered_metrics, metadata = self.voi_filter.filter_metrics(filterable_metrics)
        
        # Add back non-filterable fields
        filtered_metrics["timestamp"] = metrics.get("timestamp")
        filtered_metrics["cycle"] = metrics.get("cycle")
        filtered_metrics["node_id"] = metrics.get("node_id")
        filtered_metrics["voi_metadata"] = metadata
        
        # Update stats
        original_count = len(filterable_metrics)
        filtered_count = len(filtered_metrics) - 4  # minus non-filterable fields
        self.stats["metrics_sent"] += filtered_count
        self.stats["metrics_filtered"] += (original_count - filtered_count)
        
        if original_count > 0:
            bandwidth_saved = ((original_count - filtered_count) / original_count) * 100
            self.stats["bandwidth_saved"] = bandwidth_saved
        
        logger.debug(
            f"Filtered metrics: {original_count} -> {filtered_count} "
            f"({bandwidth_saved:.1f}% saved)"
        )
        
        return filtered_metrics
    
    def prepare_gossip_message(self) -> Dict[str, Any]:
        """
        Prepare message for gossiping to other nodes
        
        Returns:
            Gossip message dictionary
        """
        # Collect fresh metrics
        raw_metrics = self.collect_metrics()
        
        # Filter metrics if VoI is enabled
        metrics_to_send = self.filter_metrics_for_gossip(raw_metrics)
        
        # Store locally
        self.local_metrics[self.current_cycle] = raw_metrics
        
        # Prepare gossip message
        message = {
            "node_id": self.node_id,
            "cycle": self.current_cycle,
            "timestamp": time.time(),
            "metrics": metrics_to_send,
            "voi_enabled": self.enable_voi,
        }
        
        # Add VoI statistics if enabled
        if self.voi_filter:
            message["voi_stats"] = self.voi_filter.get_statistics()
        
        return message
    
    def receive_gossip_message(self, message: Dict[str, Any]):
        """
        Process received gossip message from another node
        
        Args:
            message: Received gossip message
        """
        try:
            sender_id = message.get("node_id")
            cycle = message.get("cycle")
            metrics = message.get("metrics")
            
            # Store received data
            key = f"{sender_id}:{cycle}"
            self.gossip_data[key] = message
            
            self.stats["gossip_messages_received"] += 1
            
            logger.debug(f"Received gossip from {sender_id} (cycle {cycle})")
            
        except Exception as e:
            logger.error(f"Error processing gossip message: {e}")
    
    def advance_cycle(self):
        """Advance to next gossip cycle"""
        self.current_cycle += 1
        self.stats["total_rounds"] += 1
        
        # Advance VoI filter round
        if self.voi_filter:
            self.voi_filter.advance_round()
        
        logger.debug(f"Advanced to cycle {self.current_cycle}")
    
    def get_node_statistics(self) -> Dict[str, Any]:
        """Get node statistics including VoI stats"""
        stats = self.stats.copy()
        
        if self.voi_filter:
            stats["voi_stats"] = self.voi_filter.get_statistics()
        
        return stats
    
    def cleanup_old_data(self, keep_last_n: int = 10):
        """
        Cleanup old local metrics to save memory
        
        Args:
            keep_last_n: Number of recent cycles to keep
        """
        if len(self.local_metrics) > keep_last_n:
            cycles_to_keep = sorted(self.local_metrics.keys())[-keep_last_n:]
            self.local_metrics = {
                cycle: self.local_metrics[cycle]
                for cycle in cycles_to_keep
            }
            logger.debug(f"Cleaned up old data, kept {keep_last_n} cycles")
    
    def export_data_for_analysis(self) -> Dict[str, Any]:
        """
        Export collected data for analysis
        
        Returns:
            Dictionary with all collected data and statistics
        """
        return {
            "node_id": self.node_id,
            "voi_enabled": self.enable_voi,
            "total_cycles": self.current_cycle,
            "statistics": self.get_node_statistics(),
            "local_metrics": self.local_metrics,
            "gossip_data": self.gossip_data,
            "config": VoIConfig.get_config_dict(),
        }
    
    def save_to_json(self, filepath: str):
        """Save node data to JSON file"""
        try:
            data = self.export_data_for_analysis()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Data saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
