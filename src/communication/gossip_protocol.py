"""
EdgeWatch Communication Protocol

This module implements the gossip-based communication protocol for EdgeWatch nodes.
It provides efficient peer-to-peer communication with adaptive filtering and fault tolerance.
"""

import asyncio
import json
import random
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ..core.utils import get_logger, NetworkUtils, SystemUtils, DataUtils

logger = get_logger("communication")

class GossipProtocol:
    """
    Implementation of the gossip-based communication protocol for EdgeWatch.
    
    Features:
    - Adaptive message filtering based on priorities
    - Failure detection and recovery
    - Load balancing across peers
    - Efficient metadata exchange
    """
    
    def __init__(self, node_instance):
        self.node = node_instance
        self.session = self._create_session()
        self.communication_stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'failed_requests': 0,
            'bytes_transmitted': 0,
            'avg_response_time': 0.0,
            'active_connections': 0
        }
        self.failure_threshold = 3
        self.retry_delays = [1, 2, 4, 8]  # Exponential backoff
        
    def _create_session(self):
        """Create HTTP session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set timeouts
        session.timeout = (5, 10)  # (connect_timeout, read_timeout)
        
        return session
    
    def send_gossip_message(self, target_node: Dict, data: Dict) -> bool:
        """
        Send gossip message to target node with error handling.
        
        Args:
            target_node: Target node information {'ip': str, 'port': int}
            data: Data to send
            
        Returns:
            bool: Success status
        """
        try:
            start_time = time.time()
            
            # Prepare URL
            url = f"http://{target_node['ip']}:{target_node.get('gossip_port', 5000)}/receive_message"
            
            # Add request tracking
            params = {'inc_round': self.node.cycle}
            
            # Send request
            response = self.session.get(url, json=data, params=params, timeout=10)
            
            # Update statistics
            response_time = time.time() - start_time
            self._update_communication_stats(True, response_time, len(json.dumps(data)))
            
            if response.status_code == 200:
                logger.debug(f"Successfully sent gossip message to {target_node['ip']}:{target_node.get('port', 5000)}")
                return True
            else:
                logger.warning(f"Gossip message failed with status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send gossip message to {target_node['ip']}: {e}")
            self._update_communication_stats(False, 0, 0)
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending gossip message: {e}")
            self._update_communication_stats(False, 0, 0)
            return False
    
    def exchange_metadata(self, target_node: Dict, metadata_payload: Dict) -> Optional[Dict]:
        """
        Exchange metadata with target node to determine what data to sync.
        
        Args:
            target_node: Target node information
            metadata_payload: Local metadata to send
            
        Returns:
            Dict: Response containing requested keys and updates, or None if failed
        """
        try:
            start_time = time.time()
            
            # Prepare URL
            url = f"http://{target_node['ip']}:{target_node.get('gossip_port', 5000)}/receive_metadata"
            
            # Send metadata
            response = self.session.post(url, json=metadata_payload, timeout=10)
            
            # Update statistics
            response_time = time.time() - start_time
            self._update_communication_stats(True, response_time, len(json.dumps(metadata_payload)))
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Metadata exchange successful with {target_node['ip']}")
                return result
            else:
                logger.warning(f"Metadata exchange failed with status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed metadata exchange with {target_node['ip']}: {e}")
            self._update_communication_stats(False, 0, 0)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in metadata exchange: {e}")
            self._update_communication_stats(False, 0, 0)
            return None
    
    def request_data(self, target_node: Dict, requested_keys: List[str]) -> Optional[Dict]:
        """
        Request specific data from target node.
        
        Args:
            target_node: Target node information
            requested_keys: List of keys to request
            
        Returns:
            Dict: Requested data or None if failed
        """
        try:
            if not requested_keys:
                return {}
            
            start_time = time.time()
            
            # Prepare request payload
            request_payload = {key: True for key in requested_keys}  # Simple request format
            
            # Prepare URL
            url = f"http://{target_node['ip']}:{target_node.get('gossip_port', 5000)}/get_requested_data"
            
            # Send request
            response = self.session.post(url, json=request_payload, timeout=15)
            
            # Update statistics
            response_time = time.time() - start_time
            self._update_communication_stats(True, response_time, len(json.dumps(request_payload)))
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Data request successful from {target_node['ip']} - {len(requested_keys)} keys")
                return result
            else:
                logger.warning(f"Data request failed with status {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed data request from {target_node['ip']}: {e}")
            self._update_communication_stats(False, 0, 0)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in data request: {e}")
            self._update_communication_stats(False, 0, 0)
            return None
    
    def ping_node(self, target_node: Dict) -> bool:
        """
        Ping target node to check availability.
        
        Args:
            target_node: Target node information
            
        Returns:
            bool: Node availability status
        """
        try:
            url = f"http://{target_node['ip']}:{target_node.get('gossip_port', 5000)}/health"
            response = self.session.get(url, timeout=5)
            
            is_alive = response.status_code == 200
            
            if is_alive:
                logger.debug(f"Node {target_node['ip']} is alive")
            else:
                logger.warning(f"Node {target_node['ip']} ping failed with status {response.status_code}")
                
            return is_alive
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Node {target_node['ip']} ping failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error pinging node {target_node['ip']}: {e}")
            return False
    
    def broadcast_to_peers(self, data: Dict, max_peers: int = None) -> Dict[str, bool]:
        """
        Broadcast data to multiple peers.
        
        Args:
            data: Data to broadcast
            max_peers: Maximum number of peers to contact (None for all)
            
        Returns:
            Dict: Results of broadcast {node_id: success_status}
        """
        results = {}
        
        if not self.node.node_list:
            logger.warning("No peers available for broadcast")
            return results
        
        # Select peers
        peers = list(self.node.node_list.values())
        if max_peers and len(peers) > max_peers:
            peers = random.sample(peers, max_peers)
        
        # Send to each peer
        for peer in peers:
            node_id = f"{peer['ip']}:{peer.get('port', 5000)}"
            success = self.send_gossip_message(peer, data)
            results[node_id] = success
            
            if not success:
                self._handle_node_failure(peer)
        
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"Broadcast completed - {success_count}/{len(peers)} successful")
        
        return results
    
    def _update_communication_stats(self, success: bool, response_time: float, bytes_sent: int):
        """Update communication statistics"""
        if success:
            self.communication_stats['messages_sent'] += 1
            self.communication_stats['bytes_transmitted'] += bytes_sent
            
            # Update average response time
            current_avg = self.communication_stats['avg_response_time']
            message_count = self.communication_stats['messages_sent']
            new_avg = (current_avg * (message_count - 1) + response_time) / message_count
            self.communication_stats['avg_response_time'] = new_avg
        else:
            self.communication_stats['failed_requests'] += 1
    
    def _handle_node_failure(self, failed_node: Dict):
        """Handle node failure by updating failure counters"""
        node_id = f"{failed_node['ip']}:{failed_node.get('port', 5000)}"
        
        if node_id in self.node.node_list:
            # Increment failure count
            self.node.node_list[node_id]['failure_count'] = \
                self.node.node_list[node_id].get('failure_count', 0) + 1
            
            # Remove node if failure threshold exceeded
            if self.node.node_list[node_id]['failure_count'] >= self.failure_threshold:
                logger.warning(f"Removing failed node {node_id} after {self.failure_threshold} failures")
                self.node.remove_peer_node(failed_node['ip'], failed_node.get('port', 5000))
    
    def get_communication_stats(self) -> Dict:
        """Get current communication statistics"""
        return {
            **self.communication_stats,
            'active_peers': len(self.node.node_list),
            'session_info': {
                'max_retries': 3,
                'timeout': self.session.timeout,
                'active_adapters': len(self.session.adapters)
            }
        }
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.session.close()
            logger.info("Communication protocol cleanup completed")
        except Exception as e:
            logger.error(f"Error during communication cleanup: {e}")


class MessageFilter:
    """
    Intelligent message filtering to reduce network overhead.
    """
    
    def __init__(self):
        self.priority_weights = {
            'high': 1.0,
            'medium': 0.7,
            'low': 0.4
        }
        self.recent_messages = {}  # Cache to avoid duplicate messages
        self.cache_ttl = 300  # 5 minutes
    
    def should_send_message(self, message: Dict, target_node: Dict, priority: str = 'medium') -> bool:
        """
        Determine if message should be sent based on filtering criteria.
        
        Args:
            message: Message to evaluate
            target_node: Target node information
            priority: Message priority ('high', 'medium', 'low')
            
        Returns:
            bool: Whether to send the message
        """
        try:
            # Always send high priority messages
            if priority == 'high':
                return True
            
            # Check for duplicate messages
            message_hash = DataUtils.calculate_hash(message)
            node_id = f"{target_node['ip']}:{target_node.get('port', 5000)}"
            cache_key = f"{node_id}:{message_hash}"
            
            current_time = time.time()
            
            # Clean old cache entries
            self._clean_cache(current_time)
            
            # Check if recently sent
            if cache_key in self.recent_messages:
                last_sent = self.recent_messages[cache_key]
                if current_time - last_sent < self.cache_ttl * self.priority_weights.get(priority, 0.5):
                    return False
            
            # Mark as sent
            self.recent_messages[cache_key] = current_time
            return True
            
        except Exception as e:
            logger.error(f"Error in message filtering: {e}")
            return True  # Default to sending on error
    
    def _clean_cache(self, current_time: float):
        """Clean expired cache entries"""
        expired_keys = [
            key for key, timestamp in self.recent_messages.items()
            if current_time - timestamp > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.recent_messages[key]
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")


class AdaptiveScheduler:
    """
    Adaptive scheduling for communication based on network conditions.
    """
    
    def __init__(self):
        self.base_interval = 2.0  # Base gossip interval in seconds
        self.min_interval = 0.5
        self.max_interval = 10.0
        self.adjustment_factor = 0.1
        self.network_load_threshold = 0.8
        
    def calculate_next_interval(self, success_rate: float, network_load: float) -> float:
        """
        Calculate optimal next communication interval.
        
        Args:
            success_rate: Recent communication success rate (0.0 - 1.0)
            network_load: Current network load (0.0 - 1.0)
            
        Returns:
            float: Next interval in seconds
        """
        try:
            # Start with base interval
            interval = self.base_interval
            
            # Adjust based on success rate
            if success_rate < 0.5:
                # Poor success rate - increase interval
                interval *= (1 + self.adjustment_factor * 2)
            elif success_rate > 0.9:
                # Good success rate - decrease interval
                interval *= (1 - self.adjustment_factor)
            
            # Adjust based on network load
            if network_load > self.network_load_threshold:
                interval *= (1 + self.adjustment_factor * 3)
            
            # Ensure within bounds
            interval = max(self.min_interval, min(self.max_interval, interval))
            
            return interval
            
        except Exception as e:
            logger.error(f"Error calculating next interval: {e}")
            return self.base_interval


def create_communication_protocol(node_instance):
    """Factory function to create communication protocol instance"""
    return GossipProtocol(node_instance)
