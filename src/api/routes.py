"""
EdgeWatch API Routes

This module defines all REST API endpoints for the EdgeWatch monitoring system.
It provides routes for node management, monitoring configuration, alerting,
and system status.
"""

from flask import request, jsonify, Blueprint
import json
import time
import logging

logger = logging.getLogger(__name__)

def create_api_routes(app, daemon, health_monitor, gossip_protocol):
    """Create and register API routes with the Flask application"""
    
    api = Blueprint('api', __name__, url_prefix='/api')
    
    # Nodes endpoints
    @api.route('/nodes', methods=['GET'])
    def get_nodes():
        """Get all monitored nodes"""
        try:
            nodes = daemon.get_all_nodes()
            return jsonify(nodes)
        except Exception as e:
            logger.error(f"Error getting nodes: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/nodes', methods=['POST'])
    def create_node():
        """Add a new node to monitoring"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            required_fields = ['name', 'ip_address', 'port']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            node_id = daemon.add_node(data)
            return jsonify({'id': node_id, 'status': 'created'}), 201
            
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/nodes/<node_id>', methods=['GET'])
    def get_node(node_id):
        """Get information about a specific node"""
        try:
            node = daemon.get_node(node_id)
            if not node:
                return jsonify({'error': 'Node not found'}), 404
            return jsonify(node)
        except Exception as e:
            logger.error(f"Error getting node {node_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/nodes/<node_id>/health', methods=['GET'])
    def get_node_health(node_id):
        """Get health status of a specific node"""
        try:
            health = health_monitor.get_node_health(node_id)
            if not health:
                return jsonify({'error': 'Node not found or not monitored'}), 404
            return jsonify(health)
        except Exception as e:
            logger.error(f"Error getting node health {node_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Metrics endpoints
    @api.route('/metrics', methods=['GET'])
    def get_metrics():
        """Get system metrics"""
        try:
            node_id = request.args.get('node_id')
            metric_type = request.args.get('type')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            
            metrics = daemon.get_metrics(
                node_id=node_id,
                metric_type=metric_type,
                start_time=start_time,
                end_time=end_time
            )
            return jsonify(metrics)
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/metrics', methods=['POST'])
    def submit_metrics():
        """Submit metrics data"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            daemon.store_metrics(data)
            return jsonify({'status': 'stored'}), 201
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Alerts endpoints
    @api.route('/alerts', methods=['GET'])
    def get_alerts():
        """Get all alerts"""
        try:
            status = request.args.get('status')
            severity = request.args.get('severity')
            
            alerts = daemon.get_alerts(status=status, severity=severity)
            return jsonify(alerts)
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/alerts', methods=['POST'])
    def create_alert_rule():
        """Create a new alert rule"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            rule_id = daemon.create_alert_rule(data)
            return jsonify({'id': rule_id, 'status': 'created'}), 201
            
        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Gossip protocol endpoints
    @api.route('/gossip/status', methods=['GET'])
    def get_gossip_status():
        """Get gossip protocol status"""
        try:
            status = gossip_protocol.get_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting gossip status: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/gossip/peers', methods=['GET'])
    def get_gossip_peers():
        """Get known gossip peers"""
        try:
            peers = gossip_protocol.get_peers()
            return jsonify(peers)
        except Exception as e:
            logger.error(f"Error getting gossip peers: {e}")
            return jsonify({'error': str(e)}), 500
    
    # System endpoints
    @api.route('/system/status', methods=['GET'])
    def get_system_status():
        """Get overall system status"""
        try:
            status = {
                'daemon': daemon.get_status(),
                'health_monitor': health_monitor.get_status(),
                'gossip_protocol': gossip_protocol.get_status(),
                'timestamp': time.time()
            }
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/system/info', methods=['GET'])
    def get_system_info():
        """Get system information"""
        try:
            info = {
                'node_id': daemon.node_id,
                'version': '1.0.0',
                'uptime': daemon.get_uptime(),
                'cluster_mode': daemon.cluster_mode,
                'is_primary': daemon.is_primary_node,
                'peer_count': len(gossip_protocol.get_peers()),
                'monitored_nodes': len(daemon.get_all_nodes()),
                'active_alerts': len(daemon.get_alerts(status='active'))
            }
            return jsonify(info)
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Configuration endpoints
    @api.route('/config', methods=['GET'])
    def get_config():
        """Get current configuration"""
        try:
            config = daemon.get_configuration()
            return jsonify(config)
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return jsonify({'error': str(e)}), 500
    
    @api.route('/config', methods=['PUT'])
    def update_config():
        """Update configuration"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            daemon.update_configuration(data)
            return jsonify({'status': 'updated'})
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Dashboard endpoint
    @api.route('/dashboard/data', methods=['GET'])
    def get_dashboard_data():
        """Get data for dashboard"""
        try:
            data = {
                'nodes': daemon.get_all_nodes(),
                'system_health': health_monitor.get_system_health(),
                'recent_alerts': daemon.get_alerts(limit=10),
                'gossip_status': gossip_protocol.get_status(),
                'timestamp': time.time()
            }
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Prometheus metrics endpoint
    @api.route('/metrics/prometheus', methods=['GET'])
    def get_prometheus_metrics():
        """Get metrics in Prometheus format"""
        try:
            metrics = daemon.get_prometheus_metrics()
            return metrics, 200, {'Content-Type': 'text/plain; version=0.0.4'}
        except Exception as e:
            logger.error(f"Error getting Prometheus metrics: {e}")
            return f"# Error getting metrics: {e}\n", 500, {'Content-Type': 'text/plain'}
    
    # Register the blueprint
    app.register_blueprint(api)
    
    return api
