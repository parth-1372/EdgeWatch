import signal
import time
import requests
from flask import Flask, request, jsonify
from .edge_node import EdgeNode
from .config_manager import ConfigManager
from .utils import get_logger, SystemUtils, NetworkUtils
import threading
import logging
import json
import os
from datetime import datetime

# Initialize logger
logger = get_logger("daemon")

# Initialize Flask application
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global configuration
config = ConfigManager.instance()

@app.route('/receive_message', methods=['GET'])
def receive_message():
    """Receive and process gossip messages from other nodes"""
    try:
        node = EdgeNode.instance()
        if not node.is_alive:
            logger.warning("Received message on dead node")
            return jsonify({"error": "Node is not alive"}), 500
        
        incoming_data = request.get_json()
        if not incoming_data:
            return jsonify({"error": "No data received"}), 400
        
        # Process the incoming data
        compare_and_update_node_data(incoming_data)
        
        # Update performance statistics
        node.performance_stats['messages_received'] += 1
        
        logger.debug(f"Message received and processed successfully")
        return jsonify({"status": "OK", "timestamp": SystemUtils.get_timestamp()})
        
    except Exception as e:
        logger.error(f"Error processing received message: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/metadata', methods=['GET'])
def get_metadata():
    """Get metadata about current node state"""
    try:
        node = EdgeNode.instance()
        if not node.is_alive:
            return jsonify({"error": "Node is not alive"}), 500
        
        if not node.data:
            return jsonify({"metadata": {}})
        
        latest_entry = max(node.data.keys(), key=int)
        metadata = {}
        
        for key in node.data[latest_entry]:
            if 'counter' in node.data[latest_entry][key]:
                metadata[key] = {
                    'counter': node.data[latest_entry][key]['counter'],
                    'digest': node.data[latest_entry][key].get('digest', ''),
                    'timestamp': node.data[latest_entry][key].get('hbState', {}).get('timestamp', '')
                }
        
        logger.debug(f"Metadata requested - returning {len(metadata)} entries")
        return jsonify(metadata)
        
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        return jsonify({"error": "Internal server error"}), 500


def compare_node_data_with_metadata(data):
    """Compare incoming metadata with local data and determine what to exchange"""
    try:
        node = EdgeNode.instance()
        metadata = data.get('metadata', {})
        
        # Find sender key (first key that's not 'metadata')
        sender_key = next((key for key in data if key != 'metadata'), None)
        if not sender_key:
            logger.warning("No sender key found in metadata")
            return {'requested_keys': [], 'updates': {}}
        
        sender_data = data[sender_key]
        
        # Initialize data structure if empty
        if not node.data:
            logger.info("Node has no data yet, requesting all metadata keys")
            return {'requested_keys': list(metadata.keys()), 'updates': {}}
        
        latest_entry = max(node.data.keys(), key=int)
        all_keys = set().union(node.data[latest_entry].keys(), metadata.keys())
        all_keys.discard(sender_key)
        
        # Update flow statistics
        node.data_flow_per_round.setdefault(node.cycle, {})
        if sender_key in node.data[latest_entry]:
            node.data_flow_per_round[node.cycle].setdefault('fd', 0)
            node.data_flow_per_round[node.cycle]['fd'] += 1
        else:
            node.data_flow_per_round[node.cycle].setdefault('nd', 0)
            node.data_flow_per_round[node.cycle].setdefault('fd', 0)
            node.data_flow_per_round[node.cycle]['nd'] += 1
            node.data_flow_per_round[node.cycle]['fd'] += 1
        
        # Store sender data
        node.data[latest_entry][sender_key] = sender_data
        
        # Determine what data to request and what to send
        ips_to_request = []
        data_to_send = {}
        
        for key in all_keys:
            local_has_key = key in node.data[latest_entry]
            remote_has_key = key in metadata
            
            if local_has_key and remote_has_key:
                # Both have data - compare counters
                local_counter = node.data[latest_entry][key].get('counter')
                remote_counter = metadata[key].get('counter')
                
                if not local_counter or (remote_counter and float(remote_counter) > float(local_counter)):
                    ips_to_request.append(key)
                else:
                    data_to_send[key] = node.data[latest_entry][key]
            elif local_has_key and not remote_has_key:
                # Only local has data - send it
                data_to_send[key] = node.data[latest_entry][key]
            elif not local_has_key and remote_has_key:
                # Only remote has data - request it
                ips_to_request.append(key)
        
        logger.debug(f"Metadata comparison - requesting {len(ips_to_request)} keys, sending {len(data_to_send)} keys")
        return {'requested_keys': ips_to_request, 'updates': data_to_send}
        
    except Exception as e:
        logger.error(f"Error comparing metadata: {e}")
        return {'requested_keys': [], 'updates': {}}


@app.route('/receive_metadata', methods=['POST'])
def receive_metadata():
    """Receive and process metadata from other nodes"""
    try:
        node = EdgeNode.instance()
        if not node.is_alive:
            return jsonify({"error": "Node is not alive"}), 500
        
        incoming_data = request.get_json()
        if not incoming_data:
            return jsonify({"error": "No data received"}), 400
        
        response_data = compare_node_data_with_metadata(incoming_data)
        
        logger.debug(f"Metadata processed - response contains {len(response_data.get('requested_keys', []))} requests")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error processing metadata: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/reset_node', methods=['POST'])
def reset_node():
    """Reset node to initial state"""
    try:
        node = EdgeNode.instance()
        logger.info("Resetting node to initial state")
        
        # Stop current operations
        node.is_alive = False
        
        # Wait for threads to complete
        if node.client_thread and node.client_thread.is_alive():
            node.client_thread.join(timeout=5)
        if node.counter_thread and node.counter_thread.is_alive():
            node.counter_thread.join(timeout=5)
        
        # Reset node parameters
        node.set_params(
            ip=None, port=None, cycle=0, node_list={}, data={}, 
            is_alive=False, gossip_counter=0, failure_counter=0,
            monitoring_address=None, database_address=None,
            is_send_data_back=False, client_thread=None, counter_thread=None,
            data_flow_per_round={}, push_mode="0", client_port=None
        )
        
        logger.info("Node reset completed")
        return jsonify({"status": "OK", "message": "Node reset successfully"})
        
    except Exception as e:
        logger.error(f"Error resetting node: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/stop_node', methods=['POST'])
def stop_node():
    """Stop node operations gracefully"""
    try:
        node = EdgeNode.instance()
        logger.info("Stopping node operations")
        
        node.stop_monitoring()
        
        return jsonify({"status": "OK", "message": "Node stopped successfully"})
        
    except Exception as e:
        logger.error(f"Error stopping node: {e}")
        return jsonify({"error": "Internal server error"}), 500


def compare_and_update_node_data(incoming_data):
    """Compare and update node data with incoming information"""
    try:
        node = EdgeNode.instance()
        new_time_key = node.gossip_counter
        latest_entry = max(node.data.keys(), key=int) if node.data else new_time_key
        
        # Get incoming round information
        inc_round = int(request.args.get('inc_round', node.cycle))
        
        # Update message statistics
        node.data_flow_per_round.setdefault(node.cycle, {}).setdefault('rm', 0)
        node.data_flow_per_round[node.cycle]['rm'] += 1
        
        # Get all keys from both datasets
        all_keys = set().union(
            node.data.get(latest_entry, {}).keys(),
            incoming_data.keys()
        )
        
        # Process each key
        for key in all_keys:
            local_has_key = key in node.data.get(latest_entry, {})
            remote_has_key = key in incoming_data
            
            if local_has_key and remote_has_key:
                # Both have data - merge and update
                local_data = node.data[latest_entry][key]
                remote_data = incoming_data[key]
                
                # Handle metric updates with preservation
                if 'appState' in remote_data and 'appState' in local_data:
                    existing_metrics = set(local_data['appState'].keys())
                    incoming_metrics = set(remote_data['appState'].keys())
                    
                    # Preserve existing metrics not in incoming data
                    for metric in existing_metrics - incoming_metrics:
                        remote_data['appState'][metric] = local_data['appState'][metric]
                
                # Update statistics for metric filtering
                if 'metric_sent_flags' in remote_data:
                    sent_count = sum(1 for v in remote_data['metric_sent_flags'].values() if v)
                    filtered_count = sum(1 for v in remote_data['metric_sent_flags'].values() if not v)
                    
                    node.data_flow_per_round[node.cycle].setdefault('metrics_sent', 0)
                    node.data_flow_per_round[node.cycle].setdefault('metrics_filtered', 0)
                    node.data_flow_per_round[node.cycle]['metrics_sent'] += sent_count
                    node.data_flow_per_round[node.cycle]['metrics_filtered'] += filtered_count
                
                # Merge failure lists
                local_failures = local_data.get("hbState", {}).get("failureList", [])
                remote_failures = remote_data.get("hbState", {}).get("failureList", [])
                
                # Update data based on counter comparison
                local_counter = local_data.get('counter')
                remote_counter = remote_data.get('counter')
                
                if (remote_counter and local_counter and float(remote_counter) > float(local_counter)) or \
                   (remote_counter and not local_counter):
                    node.data.setdefault(new_time_key, {})[key] = remote_data
                    node.data_flow_per_round[node.cycle].setdefault('fd', 0)
                    node.data_flow_per_round[node.cycle]['fd'] += 1
                else:
                    node.data.setdefault(new_time_key, {})[key] = local_data
                
                # Merge failure lists
                if local_failures or remote_failures:
                    merged_failures = list(set(local_failures + remote_failures))
                    if 'hbState' not in node.data[new_time_key][key]:
                        node.data[new_time_key][key]['hbState'] = {}
                    node.data[new_time_key][key]['hbState']['failureList'] = merged_failures
                
            elif local_has_key and not remote_has_key:
                # Only local has data - preserve it
                node.data.setdefault(new_time_key, {})[key] = node.data[latest_entry][key]
            elif not local_has_key and remote_has_key:
                # Only remote has data - add it
                node.data.setdefault(new_time_key, {})[key] = incoming_data[key]
                node.data_flow_per_round[node.cycle].setdefault('nd', 0)
                node.data_flow_per_round[node.cycle].setdefault('fd', 0)
                node.data_flow_per_round[node.cycle]['nd'] += 1
                node.data_flow_per_round[node.cycle]['fd'] += 1
        
        # Send data to monitoring system if configured
        if node.is_send_data_back and node.monitoring_address:
            try:
                data_to_send = node.data.get(new_time_key, node.data.get(latest_entry, {}))
                payload = {
                    'data': data_to_send,
                    'data_flow_per_round': node.data_flow_per_round.get(node.cycle, {})
                }
                
                monitoring_url = f'http://{node.monitoring_address}:{node.client_port}/receive_node_data'
                params = {'ip': node.ip, 'port': node.port, 'round': inc_round}
                
                node.session_to_monitoring.post(monitoring_url, json=payload, params=params, timeout=5)
                logger.debug("Data sent to monitoring system")
                
            except Exception as e:
                logger.warning(f"Failed to send data to monitoring system: {e}")
        
        logger.debug(f"Node data updated - cycle {node.cycle}, keys processed: {len(all_keys)}")
        
    except Exception as e:
        logger.error(f"Error updating node data: {e}")
        raise


@app.route('/start_node', methods=['POST'])
def start_node():
    """Start node operations with configuration"""
    try:
        init_data = request.get_json()
        if not init_data:
            return jsonify({"error": "No initialization data provided"}), 400
        
        # Extract configuration
        monitoring_address = init_data.get("monitoring_address")
        client_port = init_data.get("client_port", 5000)
        database_address = init_data.get("database_address")
        node_list = init_data.get("node_list", {})
        target_count = init_data.get("target_count", 3)
        gossip_rate = init_data.get("gossip_rate", 2.0)
        node_ip = init_data.get("node_ip")
        is_send_data_back = init_data.get("is_send_data_back", False)
        push_mode = init_data.get("push_mode", "0")
        
        # Get node instance
        node = EdgeNode.instance()
        
        # Allow settling time
        time.sleep(2)
        
        # Create threads
        client_thread = threading.Thread(
            target=node.start_gossiping,
            args=(target_count, gossip_rate),
            daemon=True
        )
        counter_thread = threading.Thread(
            target=node.start_gossip_counter,
            daemon=True
        )
        
        # Configure node
        host_header = request.headers.get('Host', f'{node_ip}:5000')
        node_port = host_header.split(':')[1] if ':' in host_header else '5000'
        
        node.set_params(
            ip=node_ip,
            port=node_port,
            cycle=0,
            node_list=node_list,
            data={},
            is_alive=True,
            gossip_counter=0,
            failure_counter=0,
            monitoring_address=monitoring_address,
            database_address=database_address,
            is_send_data_back=is_send_data_back,
            client_thread=client_thread,
            counter_thread=counter_thread,
            data_flow_per_round={},
            push_mode=push_mode,
            client_port=client_port
        )
        
        # Start threads
        client_thread.start()
        counter_thread.start()
        
        logger.info(f"EdgeWatch node started - IP: {node_ip}, Port: {node_port}, Target: {target_count}")
        
        return jsonify({
            "status": "OK",
            "message": "Node started successfully",
            "node_id": f"{node_ip}:{node_port}",
            "timestamp": SystemUtils.get_timestamp()
        })
        
    except Exception as e:
        logger.error(f"Error starting node: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/register_new_node', methods=['POST'])
def register_new_node():
    """Register a new node in the network"""
    try:
        node = EdgeNode.instance()
        new_node_data = request.get_json()
        
        if not new_node_data:
            return jsonify({"error": "No node data provided"}), 400
        
        # Add to node list
        node_ip = new_node_data.get('ip')
        node_port = new_node_data.get('port')
        
        if node_ip and node_port:
            node.add_peer_node(node_ip, node_port)
            logger.info(f"New node registered: {node_ip}:{node_port}")
            
            return jsonify({
                "status": "OK",
                "message": "Node registered successfully",
                "registered_nodes": len(node.node_list)
            })
        else:
            return jsonify({"error": "Invalid node data - IP and port required"}), 400
            
    except Exception as e:
        logger.error(f"Error registering new node: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_data_from_node', methods=['GET'])
def get_data_from_node():
    """Get all data from node"""
    try:
        node = EdgeNode.instance()
        return jsonify({
            "data": node.data,
            "timestamp": SystemUtils.get_timestamp(),
            "node_id": node.node_id
        })
    except Exception as e:
        logger.error(f"Error getting node data: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_recent_data_from_node', methods=['GET'])
def get_recent_data_from_node():
    """Get most recent data from node"""
    try:
        node = EdgeNode.instance()
        if not node.data:
            return jsonify({"data": {}, "message": "No data available"})
        
        latest_entry = max(node.data.keys(), key=int)
        return jsonify({
            "data": node.data[latest_entry],
            "timestamp": SystemUtils.get_timestamp(),
            "cycle": latest_entry,
            "node_id": node.node_id
        })
    except Exception as e:
        logger.error(f"Error getting recent data: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_nodelist_from_node', methods=['GET'])
def get_nodelist_from_node():
    """Get list of connected nodes"""
    try:
        node = EdgeNode.instance()
        return jsonify({
            "node_list": node.node_list,
            "count": len(node.node_list),
            "timestamp": SystemUtils.get_timestamp()
        })
    except Exception as e:
        logger.error(f"Error getting node list: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/node_status', methods=['GET'])
def get_node_status():
    """Get comprehensive node status"""
    try:
        node = EdgeNode.instance()
        status = node.get_node_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting node status: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/metrics_priority_stats', methods=['GET'])
def get_metrics_priority_stats():
    """Get statistics about priority-based metric filtering"""
    try:
        node = EdgeNode.instance()
        
        if not node.data:
            return jsonify({"error": "No data available"})
        
        # Calculate statistics
        total_sent = 0
        total_filtered = 0
        per_round_stats = {}
        
        for round_num, stats in node.data_flow_per_round.items():
            sent = stats.get('metrics_sent', 0)
            filtered = stats.get('metrics_filtered', 0)
            per_round_stats[round_num] = {
                'metrics_sent': sent,
                'metrics_filtered': filtered
            }
            total_sent += sent
            total_filtered += filtered
        
        # Calculate bandwidth savings
        total_metrics = total_sent + total_filtered
        bandwidth_savings = round(100 * total_filtered / total_metrics if total_metrics > 0 else 0, 2)
        
        return jsonify({
            'total_metrics_sent': total_sent,
            'total_metrics_filtered': total_filtered,
            'bandwidth_savings_percent': bandwidth_savings,
            'per_round_stats': per_round_stats,
            'node_id': node.node_id,
            'timestamp': SystemUtils.get_timestamp()
        })
        
    except Exception as e:
        logger.error(f"Error getting metrics stats: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        node = EdgeNode.instance()
        return jsonify({
            "status": "healthy" if node.is_alive else "inactive",
            "timestamp": SystemUtils.get_timestamp(),
            "uptime": SystemUtils.format_duration(time.time() - node.performance_stats.get('startup_time', time.time())),
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with basic information"""
    return jsonify({
        "service": "EdgeWatch",
        "description": "Decentralized Edge Monitoring System",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/node_status", 
            "/get_recent_data_from_node",
            "/get_nodelist_from_node",
            "/metrics_priority_stats"
        ]
    })


def create_app():
    """Create and configure Flask application"""
    # Initialize logging
    from .utils import LoggingManager
    LoggingManager.setup_logging(
        log_level=config.get('Logging', 'log_level', 'INFO'),
        log_file=config.get('Logging', 'log_file', 'logs/edgewatch.log')
    )
    
    logger.info("EdgeWatch daemon application created")
    return app


if __name__ == "__main__":
    # Create application
    application = create_app()
    
    # Get configuration
    host = config.get('Network', 'bind_host', '0.0.0.0')
    port = config.get_int('Network', 'daemon_port', 5000)
    debug = config.get_boolean('EdgeWatch', 'debug_mode', False)
    
    logger.info(f"Starting EdgeWatch daemon on {host}:{port}")
    
    # Start Flask application
    application.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=False
    )
