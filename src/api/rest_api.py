"""
EdgeWatch REST API

This module provides comprehensive REST API endpoints for monitoring and managing EdgeWatch nodes.
Includes endpoints for data retrieval, node management, statistics, and administrative functions.
"""

from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import threading
from typing import Dict, List, Optional, Any
import time

from ..core.edge_node import EdgeNode
from ..core.config_manager import ConfigManager
from ..client.query_interface import create_query_client, QueryResult
from ..storage.database import get_database
from ..core.utils import get_logger, SystemUtils, NetworkUtils

logger = get_logger("api")

# Create Blueprint for API routes
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

class EdgeWatchAPI:
    """
    REST API service for EdgeWatch monitoring system.
    Provides endpoints for data access, node management, and system monitoring.
    """
    
    def __init__(self):
        self.config = ConfigManager.instance()
        self.database = get_database()
        self.query_client = None
        self.api_stats = {
            'requests_count': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'start_time': time.time()
        }
        self._init_query_client()
    
    def _init_query_client(self):
        """Initialize query client with known nodes"""
        try:
            node = EdgeNode.instance()
            if node.node_list:
                node_list = [
                    {'ip': info['ip'], 'port': info['port']}
                    for info in node.node_list.values()
                ]
                self.query_client = create_query_client(node_list)
                logger.info(f"Query client initialized with {len(node_list)} nodes")
        except Exception as e:
            logger.warning(f"Failed to initialize query client: {e}")
            self.query_client = create_query_client([])
    
    def _update_api_stats(self, success: bool, response_time: float):
        """Update API statistics"""
        self.api_stats['requests_count'] += 1
        
        if success:
            self.api_stats['successful_requests'] += 1
        else:
            self.api_stats['failed_requests'] += 1
        
        # Update average response time
        current_avg = self.api_stats['avg_response_time']
        request_count = self.api_stats['requests_count']
        new_avg = (current_avg * (request_count - 1) + response_time) / request_count
        self.api_stats['avg_response_time'] = new_avg

# Global API instance
api_service = EdgeWatchAPI()

def track_request_time(func):
    """Decorator to track API request time and success"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            api_service._update_api_stats(True, response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            api_service._update_api_stats(False, response_time)
            logger.error(f"API error in {func.__name__}: {e}")
            return jsonify({"error": "Internal server error", "message": str(e)}), 500
    
    wrapper.__name__ = func.__name__
    return wrapper

# Node Management Endpoints
@api_bp.route('/nodes', methods=['GET'])
@track_request_time
def get_nodes():
    """Get list of all known nodes"""
    try:
        node = EdgeNode.instance()
        nodes = []
        
        for node_id, node_info in node.node_list.items():
            nodes.append({
                'node_id': node_id,
                'ip': node_info.get('ip'),
                'port': node_info.get('port'),
                'last_seen': node_info.get('last_seen'),
                'failure_count': node_info.get('failure_count', 0),
                'is_healthy': node_info.get('failure_count', 0) < 3
            })
        
        return jsonify({
            'nodes': nodes,
            'total_count': len(nodes),
            'healthy_count': len([n for n in nodes if n['is_healthy']]),
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting nodes: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/nodes/<node_id>', methods=['GET'])
@track_request_time
def get_node_details(node_id):
    """Get detailed information about a specific node"""
    try:
        node = EdgeNode.instance()
        
        if node_id not in node.node_list:
            return jsonify({"error": "Node not found"}), 404
        
        node_info = node.node_list[node_id]
        
        # Get recent data if available
        recent_data = None
        try:
            ip, port = node_id.split(':')
            if api_service.query_client:
                query_result = api_service.query_client.query_node_data(ip, int(port), quorum_size=1)
                if query_result.status == QueryResult.SUCCESS:
                    recent_data = query_result.data
        except Exception as e:
            logger.warning(f"Failed to get recent data for {node_id}: {e}")
        
        return jsonify({
            'node_id': node_id,
            'info': node_info,
            'recent_data': recent_data,
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting node details: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/nodes', methods=['POST'])
@track_request_time
def add_node():
    """Add a new node to the network"""
    try:
        data = request.get_json()
        if not data or 'ip' not in data or 'port' not in data:
            return jsonify({"error": "IP and port are required"}), 400
        
        node = EdgeNode.instance()
        success = node.add_peer_node(data['ip'], data['port'])
        
        if success:
            # Update query client
            if api_service.query_client:
                api_service.query_client.add_node(data['ip'], data['port'])
            
            return jsonify({
                "message": "Node added successfully",
                "node_id": f"{data['ip']}:{data['port']}"
            }), 201
        else:
            return jsonify({"error": "Failed to add node or node already exists"}), 400
    
    except Exception as e:
        logger.error(f"Error adding node: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/nodes/<node_id>', methods=['DELETE'])
@track_request_time
def remove_node(node_id):
    """Remove a node from the network"""
    try:
        node = EdgeNode.instance()
        
        if node_id not in node.node_list:
            return jsonify({"error": "Node not found"}), 404
        
        ip, port = node_id.split(':')
        success = node.remove_peer_node(ip, int(port))
        
        if success:
            # Update query client
            if api_service.query_client:
                api_service.query_client.remove_node(ip, int(port))
            
            return jsonify({"message": "Node removed successfully"})
        else:
            return jsonify({"error": "Failed to remove node"}), 500
    
    except Exception as e:
        logger.error(f"Error removing node: {e}")
        return jsonify({"error": str(e)}), 500

# Data Query Endpoints
@api_bp.route('/data/query', methods=['POST'])
@track_request_time
def query_node_data():
    """Query data for specific nodes using consensus"""
    try:
        data = request.get_json()
        if not data or 'target_ip' not in data or 'target_port' not in data:
            return jsonify({"error": "target_ip and target_port are required"}), 400
        
        target_ip = data['target_ip']
        target_port = int(data['target_port'])
        quorum_size = data.get('quorum_size', 3)
        
        if not api_service.query_client:
            api_service._init_query_client()
        
        if not api_service.query_client:
            return jsonify({"error": "Query client not available"}), 503
        
        result = api_service.query_client.query_node_data(target_ip, target_port, quorum_size)
        
        response_data = {
            'status': result.status.value,
            'data': result.data,
            'metadata': result.metadata,
            'messages_sent': result.messages_sent,
            'response_time': result.response_time,
            'nodes_contacted': result.nodes_contacted,
            'consensus_achieved': result.consensus_achieved,
            'timestamp': SystemUtils.get_timestamp()
        }
        
        if result.error_message:
            response_data['error_message'] = result.error_message
        
        status_code = 200 if result.status == QueryResult.SUCCESS else 400
        return jsonify(response_data), status_code
    
    except Exception as e:
        logger.error(f"Error querying node data: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/data/all', methods=['GET'])
@track_request_time
def get_all_data():
    """Get data for all known nodes"""
    try:
        quorum_size = request.args.get('quorum_size', 2, type=int)
        
        if not api_service.query_client:
            api_service._init_query_client()
        
        if not api_service.query_client:
            return jsonify({"error": "Query client not available"}), 503
        
        results = api_service.query_client.get_all_nodes_data(quorum_size)
        
        formatted_results = {}
        for node_id, result in results.items():
            formatted_results[node_id] = {
                'status': result.status.value,
                'data': result.data,
                'response_time': result.response_time,
                'consensus_achieved': result.consensus_achieved
            }
            if result.error_message:
                formatted_results[node_id]['error_message'] = result.error_message
        
        return jsonify({
            'results': formatted_results,
            'total_nodes': len(results),
            'successful_queries': len([r for r in results.values() if r.status == QueryResult.SUCCESS]),
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting all data: {e}")
        return jsonify({"error": str(e)}), 500

# System Status Endpoints
@api_bp.route('/status', methods=['GET'])
@track_request_time
def get_system_status():
    """Get comprehensive system status"""
    try:
        node = EdgeNode.instance()
        system_info = SystemUtils.get_system_info()
        
        # Health check nodes
        health_status = {}
        if api_service.query_client:
            health_status = api_service.query_client.health_check_nodes()
        
        return jsonify({
            'system': {
                'node_id': node.node_id,
                'is_alive': node.is_alive,
                'cycle': node.cycle,
                'gossip_counter': node.gossip_counter,
                'uptime': SystemUtils.format_duration(time.time() - node.performance_stats.get('startup_time', time.time())),
                'version': '1.0.0'
            },
            'network': {
                'connected_nodes': len(node.node_list),
                'healthy_nodes': len([n for n in node.node_list.values() if n.get('failure_count', 0) < 3]),
                'node_health': health_status
            },
            'performance': node.performance_stats,
            'hardware': {
                'cpu_count': system_info['cpu_count'],
                'memory_total': SystemUtils.format_bytes(system_info['memory_total']),
                'platform': system_info['platform']
            },
            'api_stats': api_service.api_stats,
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/metrics', methods=['GET'])
@track_request_time
def get_metrics():
    """Get system metrics and statistics"""
    try:
        node = EdgeNode.instance()
        
        # Get query client stats
        query_stats = {}
        if api_service.query_client:
            query_stats = api_service.query_client.get_query_statistics()
        
        # Get database stats
        db_stats = api_service.database.get_database_stats()
        
        return jsonify({
            'node_metrics': {
                'data_entries': len(node.data),
                'cycles_completed': node.cycle,
                'gossip_counter': node.gossip_counter,
                'data_flow_stats': node.data_flow_per_round
            },
            'query_metrics': query_stats,
            'database_metrics': db_stats,
            'api_metrics': api_service.api_stats,
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"error": str(e)}), 500

# Administrative Endpoints
@api_bp.route('/admin/reset', methods=['POST'])
@track_request_time
def admin_reset():
    """Reset the node (admin only)"""
    try:
        # This would typically require authentication
        node = EdgeNode.instance()
        node.stop_monitoring()
        
        return jsonify({
            "message": "Node reset initiated",
            "timestamp": SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error resetting node: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/admin/config', methods=['GET'])
@track_request_time
def get_config():
    """Get current configuration"""
    try:
        config = ConfigManager.instance()
        
        config_data = {}
        for section in config.sections():
            config_data[section] = config.get_section(section)
        
        return jsonify({
            'configuration': config_data,
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/admin/config', methods=['PUT'])
@track_request_time
def update_config():
    """Update configuration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Configuration data required"}), 400
        
        config = ConfigManager.instance()
        
        updated_sections = []
        for section, values in data.items():
            for key, value in values.items():
                config.set(section, key, value)
                updated_sections.append(f"{section}.{key}")
        
        return jsonify({
            "message": "Configuration updated",
            "updated": updated_sections,
            "timestamp": SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return jsonify({"error": str(e)}), 500

# Database Endpoints
@api_bp.route('/database/stats', methods=['GET'])
@track_request_time
def get_database_stats():
    """Get database statistics"""
    try:
        stats = api_service.database.get_database_stats()
        return jsonify({
            'database_stats': stats,
            'timestamp': SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/database/cleanup', methods=['POST'])
@track_request_time
def cleanup_database():
    """Clean up old database records"""
    try:
        data = request.get_json() or {}
        retention_days = data.get('retention_days', 30)
        
        api_service.database.cleanup_old_data(retention_days)
        
        return jsonify({
            "message": f"Database cleanup completed for data older than {retention_days} days",
            "timestamp": SystemUtils.get_timestamp()
        })
    
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")
        return jsonify({"error": str(e)}), 500

# Error handlers
@api_bp.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@api_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@api_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def create_api_app(config_override=None):
    """Create Flask application with API blueprint"""
    app = Flask(__name__)
    
    # Enable CORS for web interfaces
    CORS(app)
    
    # Configuration
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    if config_override:
        app.config.update(config_override)
    
    # Register blueprint
    app.register_blueprint(api_bp)
    
    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            "service": "EdgeWatch API",
            "version": "1.0.0",
            "description": "REST API for EdgeWatch Distributed Monitoring System",
            "api_version": "v1",
            "endpoints": {
                "nodes": "/api/v1/nodes",
                "data": "/api/v1/data",
                "status": "/api/v1/status",
                "metrics": "/api/v1/metrics",
                "admin": "/api/v1/admin"
            },
            "timestamp": SystemUtils.get_timestamp()
        })
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return jsonify({
            "status": "healthy",
            "timestamp": SystemUtils.get_timestamp()
        })
    
    logger.info("EdgeWatch API application created")
    return app

def start_api_server(host='0.0.0.0', port=8080, debug=False):
    """Start the API server"""
    app = create_api_app()
    logger.info(f"Starting EdgeWatch API server on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)
