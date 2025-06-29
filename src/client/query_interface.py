"""
EdgeWatch Query Interface

This module provides a comprehensive query interface for retrieving data from EdgeWatch nodes.
Implements consensus-based queries with fault tolerance and load balancing.
"""

import random
import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
import requests
from requests.exceptions import RequestException
import json

from ..core.config_manager import ConfigManager
from ..core.utils import get_logger, NetworkUtils, SystemUtils
from ..storage.database import get_database

logger = get_logger("query_interface")

class QueryResult(Enum):
    """Query result status codes"""
    SUCCESS = "success"
    CONSENSUS_FAILED = "consensus_failed"
    INSUFFICIENT_RESPONSES = "insufficient_responses"
    NODE_UNREACHABLE = "node_unreachable"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class QueryResponse:
    """Structured query response"""
    status: QueryResult
    data: Optional[Dict] = None
    metadata: Optional[Dict] = None
    messages_sent: int = 0
    response_time: float = 0.0
    nodes_contacted: int = 0
    consensus_achieved: bool = False
    error_message: Optional[str] = None

class EdgeWatchQueryClient:
    """
    Advanced query client for EdgeWatch distributed monitoring system.
    
    Features:
    - Consensus-based data retrieval
    - Fault-tolerant querying
    - Load balancing across nodes
    - Caching and optimization
    - Flexible query options
    """
    
    def __init__(self, node_list: List[Dict] = None, timeout: int = 10):
        self.config = ConfigManager.instance()
        self.node_list = node_list or []
        self.timeout = timeout
        self.session = self._create_session()
        self.database = get_database()
        
        # Query statistics
        self.query_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'avg_response_time': 0.0,
            'consensus_failures': 0,
            'nodes_failures': {}
        }
        
        # Cache for recent queries
        self.query_cache = {}
        self.cache_ttl = self.config.get_int('EdgeWatch', 'query_cache_ttl', 60)
        self.cache_lock = threading.RLock()
        
    def _create_session(self):
        """Create HTTP session with optimized settings"""
        session = requests.Session()
        session.timeout = self.timeout
        
        # Connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=2
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def add_node(self, ip: str, port: int, gossip_port: int = None):
        """Add a node to the query client's node list"""
        node = {
            'ip': ip,
            'port': str(port),
            'gossip_port': str(gossip_port or port),
            'failures': 0,
            'last_seen': time.time()
        }
        
        # Avoid duplicates
        node_id = f"{ip}:{port}"
        existing = next((n for n in self.node_list if f"{n['ip']}:{n['port']}" == node_id), None)
        
        if not existing:
            self.node_list.append(node)
            logger.info(f"Added node {node_id} to query client")
        else:
            logger.debug(f"Node {node_id} already exists in query client")
    
    def remove_node(self, ip: str, port: int):
        """Remove a node from the query client's node list"""
        node_id = f"{ip}:{port}"
        self.node_list = [n for n in self.node_list if f"{n['ip']}:{n['port']}" != node_id]
        logger.info(f"Removed node {node_id} from query client")
    
    def query_node_data(self, target_node_ip: str, target_node_port: int, 
                       quorum_size: int = 3, use_docker_ip: str = None) -> QueryResponse:
        """
        Query data for a specific target node using consensus.
        
        Args:
            target_node_ip: IP of the target node to query data for
            target_node_port: Port of the target node
            quorum_size: Number of nodes to query for consensus
            use_docker_ip: Docker IP override for containerized environments
            
        Returns:
            QueryResponse: Structured response with data and metadata
        """
        start_time = time.time()
        self.query_stats['total_queries'] += 1
        
        try:
            # Check cache first
            cache_key = f"{target_node_ip}:{target_node_port}"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.debug(f"Returning cached result for {cache_key}")
                return cached_result
            
            # Validate inputs
            if quorum_size > len(self.node_list):
                logger.warning(f"Quorum size {quorum_size} exceeds available nodes {len(self.node_list)}")
                quorum_size = min(quorum_size, len(self.node_list))
            
            if quorum_size < 1:
                return QueryResponse(
                    status=QueryResult.INSUFFICIENT_RESPONSES,
                    error_message="No nodes available for querying"
                )
            
            # Select random nodes for querying
            available_nodes = [n for n in self.node_list if n.get('failures', 0) < 3]
            if len(available_nodes) < quorum_size:
                logger.warning("Insufficient healthy nodes, using all available nodes")
                available_nodes = self.node_list
            
            selected_nodes = random.sample(available_nodes, min(quorum_size, len(available_nodes)))
            
            # Query metadata from selected nodes
            metadata_results = self._query_metadata_parallel(selected_nodes, target_node_ip, 
                                                           target_node_port, use_docker_ip)
            
            if not metadata_results:
                return QueryResponse(
                    status=QueryResult.NODE_UNREACHABLE,
                    nodes_contacted=len(selected_nodes),
                    response_time=time.time() - start_time,
                    error_message="No nodes responded to metadata query"
                )
            
            # Check consensus
            consensus_result = self._check_consensus(metadata_results)
            
            if not consensus_result['achieved']:
                self.query_stats['consensus_failures'] += 1
                return QueryResponse(
                    status=QueryResult.CONSENSUS_FAILED,
                    metadata=metadata_results,
                    nodes_contacted=len(selected_nodes),
                    messages_sent=len(metadata_results),
                    response_time=time.time() - start_time,
                    consensus_achieved=False,
                    error_message=f"Consensus failed: {consensus_result['reason']}"
                )
            
            # Get actual data from one of the consensus nodes
            data_node = random.choice(list(metadata_results.keys()))
            node_info = next(n for n in selected_nodes if f"{n['ip']}:{n['port']}" == data_node)
            
            actual_data = self._fetch_node_data(node_info, target_node_ip, target_node_port, use_docker_ip)
            
            response_time = time.time() - start_time
            
            if actual_data:
                self.query_stats['successful_queries'] += 1
                
                result = QueryResponse(
                    status=QueryResult.SUCCESS,
                    data=actual_data,
                    metadata=metadata_results,
                    messages_sent=len(metadata_results) + 1,
                    response_time=response_time,
                    nodes_contacted=len(selected_nodes),
                    consensus_achieved=True
                )
                
                # Cache successful result
                self._cache_result(cache_key, result)
                
                return result
            else:
                return QueryResponse(
                    status=QueryResult.ERROR,
                    metadata=metadata_results,
                    nodes_contacted=len(selected_nodes),
                    messages_sent=len(metadata_results) + 1,
                    response_time=response_time,
                    consensus_achieved=True,
                    error_message="Failed to fetch actual data despite consensus"
                )
                
        except Exception as e:
            logger.error(f"Unexpected error in query: {e}")
            self.query_stats['failed_queries'] += 1
            return QueryResponse(
                status=QueryResult.ERROR,
                response_time=time.time() - start_time,
                error_message=str(e)
            )
        finally:
            # Update average response time
            self._update_avg_response_time(time.time() - start_time)
    
    def _query_metadata_parallel(self, nodes: List[Dict], target_ip: str, target_port: int, 
                                docker_ip: str = None) -> Dict[str, Dict]:
        """Query metadata from multiple nodes in parallel"""
        metadata_results = {}
        
        with ThreadPoolExecutor(max_workers=min(len(nodes), 10)) as executor:
            # Submit tasks
            future_to_node = {
                executor.submit(self._query_single_metadata, node, target_ip, target_port, docker_ip): node
                for node in nodes
            }
            
            # Collect results
            for future in as_completed(future_to_node, timeout=self.timeout + 5):
                node = future_to_node[future]
                node_id = f"{node['ip']}:{node['port']}"
                
                try:
                    result = future.result()
                    if result:
                        metadata_results[node_id] = result
                        # Reset failure count on success
                        node['failures'] = 0
                        node['last_seen'] = time.time()
                except Exception as e:
                    logger.warning(f"Failed to get metadata from {node_id}: {e}")
                    self._handle_node_failure(node)
        
        return metadata_results
    
    def _query_single_metadata(self, node: Dict, target_ip: str, target_port: int, 
                              docker_ip: str = None) -> Optional[Dict]:
        """Query metadata from a single node"""
        try:
            # Determine URL
            if docker_ip:
                url = f"http://{docker_ip}:{node['port']}/metadata"
            else:
                url = f"http://{node['ip']}:{node['port']}/metadata"
            
            # Make request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            metadata = response.json()
            target_key = f"{target_ip}:{target_port}"
            
            if target_key in metadata:
                return metadata[target_key]
            else:
                logger.warning(f"Target {target_key} not found in metadata from {node['ip']}:{node['port']}")
                return None
                
        except RequestException as e:
            logger.debug(f"Request failed for {node['ip']}:{node['port']}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error querying {node['ip']}:{node['port']}: {e}")
            return None
    
    def _check_consensus(self, metadata_results: Dict[str, Dict]) -> Dict:
        """Check if consensus is achieved among metadata results"""
        if not metadata_results:
            return {'achieved': False, 'reason': 'No metadata results'}
        
        if len(metadata_results) < 2:
            return {'achieved': True, 'reason': 'Single node result'}
        
        # Get reference values
        reference_data = list(metadata_results.values())[0]
        reference_counter = reference_data.get('counter')
        reference_digest = reference_data.get('digest')
        
        # Check counter consensus
        counter_consensus = all(
            data.get('counter') == reference_counter 
            for data in metadata_results.values()
        )
        
        if not counter_consensus:
            return {
                'achieved': False, 
                'reason': 'Counter values do not match across nodes'
            }
        
        # Check digest consensus
        digest_consensus = all(
            data.get('digest') == reference_digest 
            for data in metadata_results.values()
        )
        
        if not digest_consensus:
            return {
                'achieved': False, 
                'reason': 'Digest values do not match across nodes'
            }
        
        return {'achieved': True, 'reason': 'Full consensus achieved'}
    
    def _fetch_node_data(self, node: Dict, target_ip: str, target_port: int, 
                        docker_ip: str = None) -> Optional[Dict]:
        """Fetch actual data from a node"""
        try:
            # Determine URL
            if docker_ip:
                url = f"http://{docker_ip}:{node['port']}/get_recent_data_from_node"
            else:
                url = f"http://{node['ip']}:{node['port']}/get_recent_data_from_node"
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            target_key = f"{target_ip}:{target_port}"
            
            if isinstance(data, dict) and 'data' in data:
                # New format with metadata
                node_data = data['data']
                if target_key in node_data:
                    return node_data[target_key]
            elif isinstance(data, dict) and target_key in data:
                # Legacy format
                return data[target_key]
            
            logger.warning(f"Target {target_key} not found in data from {node['ip']}:{node['port']}")
            return None
            
        except RequestException as e:
            logger.error(f"Failed to fetch data from {node['ip']}:{node['port']}: {e}")
            self._handle_node_failure(node)
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching data from {node['ip']}:{node['port']}: {e}")
            return None
    
    def _handle_node_failure(self, node: Dict):
        """Handle node failure by incrementing failure count"""
        node['failures'] = node.get('failures', 0) + 1
        node_id = f"{node['ip']}:{node['port']}"
        
        self.query_stats['nodes_failures'][node_id] = \
            self.query_stats['nodes_failures'].get(node_id, 0) + 1
        
        if node['failures'] >= 3:
            logger.warning(f"Node {node_id} marked as failed after {node['failures']} failures")
    
    def _get_cached_result(self, cache_key: str) -> Optional[QueryResponse]:
        """Get cached query result if still valid"""
        with self.cache_lock:
            if cache_key in self.query_cache:
                cached_data, timestamp = self.query_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return cached_data
                else:
                    # Remove expired cache
                    del self.query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: QueryResponse):
        """Cache query result"""
        with self.cache_lock:
            # Limit cache size
            if len(self.query_cache) > 100:
                # Remove oldest entries
                oldest_key = min(self.query_cache.keys(), 
                               key=lambda k: self.query_cache[k][1])
                del self.query_cache[oldest_key]
            
            self.query_cache[cache_key] = (result, time.time())
    
    def _update_avg_response_time(self, response_time: float):
        """Update average response time statistic"""
        current_avg = self.query_stats['avg_response_time']
        total_queries = self.query_stats['total_queries']
        
        if total_queries == 1:
            self.query_stats['avg_response_time'] = response_time
        else:
            new_avg = (current_avg * (total_queries - 1) + response_time) / total_queries
            self.query_stats['avg_response_time'] = new_avg
    
    def query_multiple_nodes(self, target_nodes: List[Tuple[str, int]], 
                           quorum_size: int = 3) -> Dict[str, QueryResponse]:
        """Query data for multiple target nodes"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(len(target_nodes), 5)) as executor:
            future_to_target = {
                executor.submit(self.query_node_data, ip, port, quorum_size): f"{ip}:{port}"
                for ip, port in target_nodes
            }
            
            for future in as_completed(future_to_target):
                target_id = future_to_target[future]
                try:
                    results[target_id] = future.result()
                except Exception as e:
                    logger.error(f"Failed to query {target_id}: {e}")
                    results[target_id] = QueryResponse(
                        status=QueryResult.ERROR,
                        error_message=str(e)
                    )
        
        return results
    
    def get_all_nodes_data(self, quorum_size: int = 2) -> Dict[str, QueryResponse]:
        """Get data for all known nodes"""
        target_nodes = [(n['ip'], int(n['port'])) for n in self.node_list]
        return self.query_multiple_nodes(target_nodes, quorum_size)
    
    def health_check_nodes(self) -> Dict[str, bool]:
        """Perform health check on all nodes"""
        results = {}
        
        def check_node(node):
            try:
                url = f"http://{node['ip']}:{node['port']}/health"
                response = self.session.get(url, timeout=5)
                return response.status_code == 200
            except:
                return False
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_node = {
                executor.submit(check_node, node): f"{node['ip']}:{node['port']}"
                for node in self.node_list
            }
            
            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                try:
                    results[node_id] = future.result()
                except:
                    results[node_id] = False
        
        return results
    
    def get_query_statistics(self) -> Dict:
        """Get query client statistics"""
        success_rate = 0
        if self.query_stats['total_queries'] > 0:
            success_rate = (self.query_stats['successful_queries'] / 
                          self.query_stats['total_queries']) * 100
        
        return {
            **self.query_stats,
            'success_rate_percent': round(success_rate, 2),
            'cache_size': len(self.query_cache),
            'available_nodes': len([n for n in self.node_list if n.get('failures', 0) < 3]),
            'total_nodes': len(self.node_list)
        }
    
    def clear_cache(self):
        """Clear query cache"""
        with self.cache_lock:
            self.query_cache.clear()
            logger.info("Query cache cleared")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.session.close()
            self.clear_cache()
            logger.info("Query client cleanup completed")
        except Exception as e:
            logger.error(f"Error during query client cleanup: {e}")


def create_query_client(node_list: List[Dict] = None, timeout: int = 10) -> EdgeWatchQueryClient:
    """Factory function to create query client"""
    return EdgeWatchQueryClient(node_list, timeout)
