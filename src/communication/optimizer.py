"""
EdgeWatch Communication Optimizer
Advanced communication protocol optimization for improved performance and reliability.
Implements adaptive protocols, message compression, and intelligent routing.
"""

import logging
import json
import zlib
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import hashlib
import socket
import struct


class MessageType(Enum):
    """Message types for communication protocol"""
    HEARTBEAT = "heartbeat"
    DATA_SYNC = "data_sync"
    QUERY_REQUEST = "query_request"
    QUERY_RESPONSE = "query_response"
    NODE_DISCOVERY = "node_discovery"
    STATUS_UPDATE = "status_update"
    GOSSIP_MESSAGE = "gossip_message"
    CONTROL_MESSAGE = "control_message"


class CompressionType(Enum):
    """Compression algorithms available"""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"


class Priority(Enum):
    """Message priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class OptimizedMessage:
    """Optimized message structure"""
    message_id: str
    sender_id: str
    recipient_id: str
    message_type: MessageType
    priority: Priority
    timestamp: float
    ttl: int
    compression: CompressionType
    payload: bytes
    checksum: str
    metadata: Dict[str, Any]
    
    def to_bytes(self) -> bytes:
        """Convert message to bytes for transmission"""
        header = {
            'id': self.message_id,
            'sender': self.sender_id,
            'recipient': self.recipient_id,
            'type': self.message_type.value,
            'priority': self.priority.value,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
            'compression': self.compression.value,
            'checksum': self.checksum,
            'metadata': self.metadata
        }
        
        header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
        header_length = len(header_json)
        payload_length = len(self.payload)
        
        # Pack: header_length (4 bytes), payload_length (4 bytes), header, payload
        return struct.pack('!II', header_length, payload_length) + header_json + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'OptimizedMessage':
        """Create message from bytes"""
        if len(data) < 8:
            raise ValueError("Invalid message format")
            
        header_length, payload_length = struct.unpack('!II', data[:8])
        
        if len(data) < 8 + header_length + payload_length:
            raise ValueError("Incomplete message data")
            
        header_json = data[8:8 + header_length].decode('utf-8')
        payload = data[8 + header_length:8 + header_length + payload_length]
        
        header = json.loads(header_json)
        
        return cls(
            message_id=header['id'],
            sender_id=header['sender'],
            recipient_id=header['recipient'],
            message_type=MessageType(header['type']),
            priority=Priority(header['priority']),
            timestamp=header['timestamp'],
            ttl=header['ttl'],
            compression=CompressionType(header['compression']),
            payload=payload,
            checksum=header['checksum'],
            metadata=header['metadata']
        )


class MessageCompressor:
    """Handles message compression and decompression"""
    
    @staticmethod
    def compress(data: bytes, compression_type: CompressionType) -> bytes:
        """Compress data using specified algorithm"""
        if compression_type == CompressionType.NONE:
            return data
        elif compression_type == CompressionType.ZLIB:
            return zlib.compress(data)
        elif compression_type == CompressionType.GZIP:
            import gzip
            return gzip.compress(data)
        else:
            raise ValueError(f"Unknown compression type: {compression_type}")
    
    @staticmethod
    def decompress(data: bytes, compression_type: CompressionType) -> bytes:
        """Decompress data using specified algorithm"""
        if compression_type == CompressionType.NONE:
            return data
        elif compression_type == CompressionType.ZLIB:
            return zlib.decompress(data)
        elif compression_type == CompressionType.GZIP:
            import gzip
            return gzip.decompress(data)
        else:
            raise ValueError(f"Unknown compression type: {compression_type}")


class AdaptiveProtocol:
    """Adaptive protocol that adjusts based on network conditions"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.logger = logging.getLogger(f"EdgeWatch.AdaptiveProtocol.{node_id}")
        
        # Network condition tracking
        self.latency_history = defaultdict(lambda: deque(maxlen=100))
        self.bandwidth_history = defaultdict(lambda: deque(maxlen=100))
        self.error_rates = defaultdict(lambda: deque(maxlen=100))
        
        # Adaptive parameters
        self.compression_thresholds = {
            'size_threshold': 1024,  # Compress messages larger than 1KB
            'latency_threshold': 100,  # Use compression if latency > 100ms
            'bandwidth_threshold': 1000000  # Use compression if bandwidth < 1MB/s
        }
        
        # Protocol statistics
        self.message_stats = {
            'sent': 0,
            'received': 0,
            'compressed': 0,
            'errors': 0,
            'retransmissions': 0
        }
        
        self._lock = threading.Lock()
    
    def should_compress(self, recipient_id: str, payload_size: int) -> CompressionType:
        """Determine if message should be compressed and which algorithm to use"""
        with self._lock:
            # Always compress large messages
            if payload_size > self.compression_thresholds['size_threshold']:
                return CompressionType.ZLIB
            
            # Check network conditions for recipient
            if recipient_id in self.latency_history:
                recent_latency = list(self.latency_history[recipient_id])[-10:]  # Last 10 measurements
                if recent_latency:
                    avg_latency = sum(recent_latency) / len(recent_latency)
                    if avg_latency > self.compression_thresholds['latency_threshold']:
                        return CompressionType.ZLIB
            
            if recipient_id in self.bandwidth_history:
                recent_bandwidth = list(self.bandwidth_history[recipient_id])[-10:]
                if recent_bandwidth:
                    avg_bandwidth = sum(recent_bandwidth) / len(recent_bandwidth)
                    if avg_bandwidth < self.compression_thresholds['bandwidth_threshold']:
                        return CompressionType.ZLIB
            
            return CompressionType.NONE
    
    def get_optimal_ttl(self, message_type: MessageType, recipient_id: str) -> int:
        """Calculate optimal TTL based on message type and network conditions"""
        base_ttl = {
            MessageType.HEARTBEAT: 30,
            MessageType.DATA_SYNC: 300,
            MessageType.QUERY_REQUEST: 60,
            MessageType.QUERY_RESPONSE: 120,
            MessageType.NODE_DISCOVERY: 600,
            MessageType.STATUS_UPDATE: 180,
            MessageType.GOSSIP_MESSAGE: 600,
            MessageType.CONTROL_MESSAGE: 30
        }
        
        ttl = base_ttl.get(message_type, 120)
        
        # Adjust based on network conditions
        with self._lock:
            if recipient_id in self.error_rates:
                recent_errors = list(self.error_rates[recipient_id])[-10:]
                if recent_errors:
                    error_rate = sum(recent_errors) / len(recent_errors)
                    if error_rate > 0.1:  # High error rate
                        ttl *= 2  # Increase TTL
        
        return ttl
    
    def update_network_stats(self, recipient_id: str, latency: float, 
                           bandwidth: float, success: bool):
        """Update network statistics for adaptive behavior"""
        with self._lock:
            self.latency_history[recipient_id].append(latency)
            self.bandwidth_history[recipient_id].append(bandwidth)
            self.error_rates[recipient_id].append(0.0 if success else 1.0)
    
    def get_network_stats(self, recipient_id: str) -> Dict[str, float]:
        """Get network statistics for a recipient"""
        with self._lock:
            stats = {
                'avg_latency': 0.0,
                'avg_bandwidth': 0.0,
                'error_rate': 0.0,
                'sample_count': 0
            }
            
            if recipient_id in self.latency_history:
                latencies = list(self.latency_history[recipient_id])
                if latencies:
                    stats['avg_latency'] = sum(latencies) / len(latencies)
                    stats['sample_count'] = len(latencies)
            
            if recipient_id in self.bandwidth_history:
                bandwidths = list(self.bandwidth_history[recipient_id])
                if bandwidths:
                    stats['avg_bandwidth'] = sum(bandwidths) / len(bandwidths)
            
            if recipient_id in self.error_rates:
                errors = list(self.error_rates[recipient_id])
                if errors:
                    stats['error_rate'] = sum(errors) / len(errors)
            
            return stats


class MessageRouter:
    """Intelligent message routing with load balancing and failover"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.logger = logging.getLogger(f"EdgeWatch.MessageRouter.{node_id}")
        
        # Routing tables
        self.direct_routes = {}  # node_id -> connection info
        self.relay_routes = defaultdict(list)  # node_id -> list of relay nodes
        self.route_costs = {}  # (src, dst) -> cost
        
        # Load balancing
        self.connection_loads = defaultdict(int)
        self.connection_limits = defaultdict(lambda: 100)  # Default connection limit
        
        self._lock = threading.Lock()
    
    def add_route(self, destination: str, next_hop: str, cost: float):
        """Add or update a route"""
        with self._lock:
            if cost == 1.0:  # Direct connection
                self.direct_routes[destination] = next_hop
            else:
                self.relay_routes[destination].append((next_hop, cost))
                self.relay_routes[destination].sort(key=lambda x: x[1])  # Sort by cost
            
            self.route_costs[(self.node_id, destination)] = cost
    
    def get_best_route(self, destination: str) -> Optional[str]:
        """Get the best route to destination considering load and cost"""
        with self._lock:
            # Try direct route first
            if destination in self.direct_routes:
                next_hop = self.direct_routes[destination]
                if self.connection_loads[next_hop] < self.connection_limits[next_hop]:
                    return next_hop
            
            # Try relay routes
            if destination in self.relay_routes:
                for next_hop, cost in self.relay_routes[destination]:
                    if self.connection_loads[next_hop] < self.connection_limits[next_hop]:
                        return next_hop
            
            return None
    
    def update_connection_load(self, connection: str, delta: int):
        """Update connection load"""
        with self._lock:
            self.connection_loads[connection] = max(0, self.connection_loads[connection] + delta)
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        with self._lock:
            return {
                'direct_routes': len(self.direct_routes),
                'relay_routes': len(self.relay_routes),
                'total_connections': len(self.connection_loads),
                'connection_loads': dict(self.connection_loads),
                'connection_limits': dict(self.connection_limits)
            }


class CommunicationOptimizer:
    """
    Main communication optimizer that coordinates adaptive protocols,
    message compression, and intelligent routing.
    """
    
    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"EdgeWatch.CommOptimizer.{node_id}")
        
        # Components
        self.adaptive_protocol = AdaptiveProtocol(node_id)
        self.message_router = MessageRouter(node_id)
        self.compressor = MessageCompressor()
        
        # Message queues by priority
        self.message_queues = {
            Priority.CRITICAL: deque(),
            Priority.HIGH: deque(),
            Priority.NORMAL: deque(),
            Priority.LOW: deque()
        }
        
        # Configuration
        self.max_message_size = self.config.get('max_message_size', 1024 * 1024)  # 1MB
        self.batch_size = self.config.get('batch_size', 10)
        self.batch_timeout = self.config.get('batch_timeout', 0.1)  # 100ms
        
        # Statistics
        self.optimization_stats = {
            'messages_processed': 0,
            'bytes_saved_compression': 0,
            'routing_decisions': 0,
            'failed_routes': 0,
            'average_processing_time': 0.0
        }
        
        self._lock = threading.Lock()
        self._processing_times = deque(maxlen=1000)
    
    def create_optimized_message(self, recipient_id: str, message_type: MessageType,
                               payload: Dict[str, Any], priority: Priority = Priority.NORMAL,
                               metadata: Optional[Dict[str, Any]] = None) -> OptimizedMessage:
        """Create an optimized message"""
        start_time = time.time()
        
        # Serialize payload
        payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        
        # Determine compression
        compression_type = self.adaptive_protocol.should_compress(recipient_id, len(payload_json))
        compressed_payload = self.compressor.compress(payload_json, compression_type)
        
        # Calculate checksum
        checksum = hashlib.sha256(compressed_payload).hexdigest()
        
        # Get optimal TTL
        ttl = self.adaptive_protocol.get_optimal_ttl(message_type, recipient_id)
        
        # Create message
        message = OptimizedMessage(
            message_id=f"{self.node_id}_{int(time.time() * 1000000)}",
            sender_id=self.node_id,
            recipient_id=recipient_id,
            message_type=message_type,
            priority=priority,
            timestamp=time.time(),
            ttl=ttl,
            compression=compression_type,
            payload=compressed_payload,
            checksum=checksum,
            metadata=metadata or {}
        )
        
        # Update statistics
        processing_time = time.time() - start_time
        with self._lock:
            self._processing_times.append(processing_time)
            self.optimization_stats['messages_processed'] += 1
            if compression_type != CompressionType.NONE:
                self.optimization_stats['bytes_saved_compression'] += len(payload_json) - len(compressed_payload)
            
            if self._processing_times:
                self.optimization_stats['average_processing_time'] = sum(self._processing_times) / len(self._processing_times)
        
        return message
    
    def process_received_message(self, message_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Process received message and return payload and metadata"""
        message = OptimizedMessage.from_bytes(message_bytes)
        
        # Verify checksum
        calculated_checksum = hashlib.sha256(message.payload).hexdigest()
        if calculated_checksum != message.checksum:
            raise ValueError("Message checksum verification failed")
        
        # Decompress payload
        decompressed_payload = self.compressor.decompress(message.payload, message.compression)
        payload = json.loads(decompressed_payload.decode('utf-8'))
        
        # Update network statistics
        processing_time = time.time() - message.timestamp
        self.adaptive_protocol.update_network_stats(
            message.sender_id, processing_time, len(message_bytes), True
        )
        
        return payload, {
            'sender_id': message.sender_id,
            'message_type': message.message_type.value,
            'priority': message.priority.value,
            'timestamp': message.timestamp,
            'ttl': message.ttl,
            'metadata': message.metadata
        }
    
    def get_next_hop(self, destination: str) -> Optional[str]:
        """Get next hop for message routing"""
        with self._lock:
            self.optimization_stats['routing_decisions'] += 1
        
        next_hop = self.message_router.get_best_route(destination)
        if next_hop is None:
            with self._lock:
                self.optimization_stats['failed_routes'] += 1
        
        return next_hop
    
    def add_route(self, destination: str, next_hop: str, cost: float = 1.0):
        """Add routing information"""
        self.message_router.add_route(destination, next_hop, cost)
    
    def update_connection_load(self, connection: str, delta: int):
        """Update connection load for load balancing"""
        self.message_router.update_connection_load(connection, delta)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics"""
        with self._lock:
            stats = self.optimization_stats.copy()
        
        stats.update({
            'adaptive_protocol': {
                'compression_decisions': self.adaptive_protocol.message_stats,
                'network_conditions': {
                    node_id: self.adaptive_protocol.get_network_stats(node_id)
                    for node_id in list(self.adaptive_protocol.latency_history.keys())[:10]  # Top 10
                }
            },
            'routing': self.message_router.get_routing_stats()
        })
        
        return stats
    
    def optimize_batch(self, messages: List[OptimizedMessage]) -> List[OptimizedMessage]:
        """Optimize a batch of messages for transmission"""
        if not messages:
            return messages
        
        # Sort by priority and destination for optimal batching
        messages.sort(key=lambda m: (m.priority.value, m.recipient_id))
        
        # Group by destination for potential message aggregation
        destination_groups = defaultdict(list)
        for message in messages:
            destination_groups[message.recipient_id].append(message)
        
        optimized_messages = []
        for destination, dest_messages in destination_groups.items():
            # For now, just return original messages
            # Future: implement message aggregation for same destination
            optimized_messages.extend(dest_messages)
        
        return optimized_messages


def create_communication_optimizer(node_id: str, config: Optional[Dict[str, Any]] = None) -> CommunicationOptimizer:
    """Factory function to create communication optimizer"""
    return CommunicationOptimizer(node_id, config)
