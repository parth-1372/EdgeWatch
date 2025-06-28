import os
import random
import time
import psutil
import requests
from .config_manager import ConfigManager
from .utils import get_logger, SystemUtils, NetworkUtils
import logging
import hashlib
import json
import math
import threading

logger = get_logger("edge_node")

# Define priority levels and update frequencies
PRIORITY_HIGH = 1     # Update every round
PRIORITY_MEDIUM = 5   # Update every 5 rounds
PRIORITY_LOW = 10     # Update every 10 rounds

# Configure priorities for different metrics
METRIC_PRIORITIES = {
    "cpu": PRIORITY_HIGH,      # CPU is critical - update every round
    "memory": PRIORITY_MEDIUM, # Memory - update every 5 rounds
    "network": PRIORITY_MEDIUM, # Network - update every 5 rounds
    "storage": PRIORITY_LOW    # Storage changes slowly - update every 10 rounds
}

# Delta thresholds for each metric (minimum change to trigger update)
METRIC_DELTAS = {
    "cpu": 5.0,      # 5% change in CPU
    "memory": 7.0,   # 7% change in memory
    "network": 15.0, # 15% change in network
    "storage": 10.0  # 10% change in storage
}

# Track last values to calculate deltas
last_metric_values = {}
# Track when each metric was last sent
last_metric_sent_round = {}

def calculate_digest(data):
    """Calculate SHA256 digest of data for integrity verification"""
    nested_dict_str = json.dumps(data, sort_keys=True)
    hash_object = hashlib.sha256()
    hash_object.update(nested_dict_str.encode('utf-8'))
    digest = hash_object.hexdigest()
    return digest

def should_send_metric(node, metric, value):
    """Determine if a metric should be sent based on priority and delta thresholds"""
    # Initialize tracking dictionaries if needed
    if metric not in last_metric_values:
        last_metric_values[metric] = value
        last_metric_sent_round[metric] = 0
        return True  # Always send first time
        
    # Get priority for this metric
    priority = METRIC_PRIORITIES.get(metric, PRIORITY_HIGH)
    
    # Calculate rounds since last sent
    rounds_since_sent = node.cycle - last_metric_sent_round[metric]
    
    # Calculate delta (percent change) for numeric metrics
    if isinstance(value, (int, float)) and isinstance(last_metric_values[metric], (int, float)) and last_metric_values[metric] != 0:
        if metric == "network" or metric == "storage":
            # For network and storage, calculate absolute change
            delta_percent = abs(value - last_metric_values[metric]) / max(value, last_metric_values[metric]) * 100
        else:
            # For CPU and memory, calculate percentage point change
            delta_percent = abs(value - last_metric_values[metric])
    else:
        delta_percent = float('inf')  # Always send non-numeric or zero-based values
        
    # Determine if we should send this metric
    should_send = False
    
    # Always send high priority metrics
    if priority == PRIORITY_HIGH:
        should_send = True
    # Send medium/low priority metrics based on schedule or significant change
    elif rounds_since_sent >= priority:
        should_send = True
    # Send if significant change detected
    elif delta_percent >= METRIC_DELTAS.get(metric, 0):
        should_send = True
        
    # Update last sent round if sending
    if should_send:
        last_metric_sent_round[metric] = node.cycle
    
    # Always update last value for future delta calculations
    last_metric_values[metric] = value
    
    # Log decision with structured information
    logger.debug(f"METRIC_PRIORITY: metric={metric}, value={value:.2f}, priority={priority}, " +
                f"delta={delta_percent:.2f}%, rounds_since_sent={rounds_since_sent}, decision={'SEND' if should_send else 'SKIP'}")
    
    return should_send

def collect_system_metrics():
    """Collect current system metrics"""
    node = EdgeNode.instance()
    network = psutil.net_io_counters().bytes_recv + psutil.net_io_counters().bytes_sent
    
    # Get current metric values
    current_metrics = {
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "network": network,
        "storage": psutil.disk_usage('/').free
    }
    
    # Determine which metrics to send based on priority and delta
    metrics_to_send = {}
    metrics_filtered = {}
    
    for metric, value in current_metrics.items():
        if should_send_metric(node, metric, value):
            metrics_to_send[metric] = value
        else:
            metrics_filtered[metric] = value
    
    # Create the data structure with only selected metrics
    app_state = {}
    for metric in metrics_to_send:
        app_state[metric] = str(metrics_to_send[metric])
    
    # Track metrics statistics for this round
    node.data_flow_per_round.setdefault(node.cycle, {})
    node.data_flow_per_round[node.cycle]['metrics_sent'] = len(metrics_to_send)
    node.data_flow_per_round[node.cycle]['metrics_filtered'] = len(metrics_filtered)
    
    # Store data about which metrics were sent this round
    metric_flags = {metric: (metric in metrics_to_send) for metric in current_metrics}
    
    data = {
        "counter": "{}".format(node.gossip_counter),
        "cycle": "{}".format(node.cycle),
        "digest": "",
        "nodeState": {
            "id": "",
            "ip": "{}".format(node.ip),
            "port": "{}".format(node.port)},
        "hbState": {
            "timestamp": "{}".format(time.time()),
            "failureCount": node.failure_counter,
            "failureList": node.failure_list,
            "nodeAlive": node.is_alive},
        "appState": app_state,
        "nfState": {},
        "metric_sent_flags": metric_flags
    }
    
    digest = calculate_digest(data)
    data["digest"] = digest
    
    return data

class EdgeNode:
    """Main EdgeWatch monitoring node implementing gossip-based communication"""
    
    _instance = None
    _initialized = False
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EdgeNode, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Initialize configuration manager
        self.config = ConfigManager.instance()
        
        # Node identification
        self.ip = None
        self.port = None
        self.node_id = None
        
        # Communication state
        self.cycle = 0
        self.gossip_counter = 0
        self.failure_counter = 0
        self.failure_list = []
        self.is_alive = False
        
        # Data management
        self.node_list = {}
        self.data = {}
        self.data_flow_per_round = {}
        self.metric_last_sent = {}
        
        # Network configuration
        self.monitoring_address = None
        self.database_address = None
        self.client_port = None
        self.push_mode = "0"
        self.is_send_data_back = False
        
        # Threading
        self.client_thread = None
        self.counter_thread = None
        self.session_to_monitoring = requests.Session()
        
        # Performance tracking
        self.performance_stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_transmitted': 0,
            'failed_connections': 0,
            'startup_time': time.time()
        }
        
        self._initialized = True
        logger.info("EdgeWatch node initialized")
    
    def initialize_from_config(self, config_file=None):
        """Initialize node from configuration file"""
        try:
            if config_file:
                self.config.load_config_file(config_file)
            
            # Load network configuration
            self.ip = self.config.get('Network', 'default_ip', NetworkUtils.get_local_ip())
            self.port = self.config.get_int('Network', 'default_port', 8080)
            self.client_port = self.config.get_int('Network', 'client_port', 5000)
            
            # Load monitoring configuration
            self.monitoring_address = self.config.get('Monitoring', 'server_address', 'localhost')
            self.database_address = self.config.get('Storage', 'database_address', 'localhost')
            self.push_mode = self.config.get('Monitoring', 'push_mode', '0')
            self.is_send_data_back = self.config.get_boolean('Monitoring', 'send_data_back', False)
            
            # Generate unique node ID
            self.node_id = f"{self.ip}:{self.port}"
            
            # Initialize data structures
            self.data = {}
            self.data_flow_per_round = {}
            
            logger.info(f"Node configured - ID: {self.node_id}, Push Mode: {self.push_mode}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize from config: {e}")
            return False
    
    def get_node_status(self):
        """Get comprehensive node status information"""
        system_info = SystemUtils.get_system_info()
        
        return {
            'node_id': self.node_id,
            'ip': self.ip,
            'port': self.port,
            'is_alive': self.is_alive,
            'cycle': self.cycle,
            'gossip_counter': self.gossip_counter,
            'failure_counter': self.failure_counter,
            'connected_nodes': len(self.node_list),
            'data_entries': len(self.data),
            'push_mode': self.push_mode,
            'performance': self.performance_stats.copy(),
            'system': {
                'cpu_count': system_info['cpu_count'],
                'memory_total': SystemUtils.format_bytes(system_info['memory_total']),
                'platform': system_info['platform'],
                'uptime': SystemUtils.format_duration(time.time() - self.performance_stats['startup_time'])
            }
        }
    
    def add_peer_node(self, ip, port):
        """Add a peer node to the network"""
        node_key = f"{ip}:{port}"
        if node_key != self.node_id:
            self.node_list[node_key] = {
                'ip': ip,
                'port': port,
                'last_seen': time.time(),
                'failure_count': 0
            }
            logger.info(f"Added peer node: {node_key}")
            return True
        return False
    
    def remove_peer_node(self, ip, port):
        """Remove a peer node from the network"""
        node_key = f"{ip}:{port}"
        if node_key in self.node_list:
            del self.node_list[node_key]
            logger.info(f"Removed peer node: {node_key}")
            return True
        return False
    
    def start_monitoring(self, target_count=3, gossip_rate=2.0):
        """Start the monitoring process with improved error handling"""
        try:
            if not self.is_alive:
                self.is_alive = True
                
                # Start gossip counter thread
                self.counter_thread = threading.Thread(
                    target=self.start_gossip_counter,
                    daemon=True
                )
                self.counter_thread.start()
                
                # Start main gossip loop
                logger.info(f"Starting EdgeWatch monitoring - Target: {target_count}, Rate: {gossip_rate}s")
                self.start_gossiping(target_count, gossip_rate)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Error in monitoring process: {e}")
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """Stop the monitoring process gracefully"""
        self.is_alive = False
        logger.info("EdgeWatch monitoring stopped")
        
        # Log final statistics
        status = self.get_node_status()
        logger.info(f"Final stats - Messages sent: {status['performance']['messages_sent']}, "
                   f"Messages received: {status['performance']['messages_received']}, "
                   f"Uptime: {status['system']['uptime']}")

    def start_gossip_counter(self):
        """Start the gossip counter thread"""
        while self.is_alive:
            self.gossip_counter += 1
            time.sleep(1)

    def start_gossiping(self, target_count, gossip_rate):
        """Start the main gossip communication loop"""
        print("Starting gossiping with target count: {} and gossip rate: {} and length of node list: {}".format(
            target_count, gossip_rate, len(self.node_list)),
            flush=True)
        while self.is_alive:
            if self.push_mode == "1":
                print("Pushing data", flush=True)
                if self.cycle % 10 == 0 and self.cycle != 0:
                    self.push_latest_data_and_delete_after_push()
            self.cycle += 1
            self.transmit(target_count)
            time.sleep(gossip_rate)

    def prepare_metadata_and_own_fresh_data(self, time_key):
        """Prepare metadata and own fresh data for transmission"""
        metadata = {}
        own_key = self.ip + ':' + self.port
        own_recent_data = self.data[time_key][own_key]
        
        # Apply priority filtering to own data
        filtered_own_data = self.get_filtered_data_by_priority(own_recent_data)
        
        for key in self.data[time_key]:
            if 'counter' in self.data[time_key][key] and key is not own_key:
                metadata[key] = self.data[time_key][key]['counter']
        
        to_send = {'metadata': metadata, own_key: filtered_own_data}
        return to_send

    def transmit(self, target_count):
        """Transmit data to randomly selected nodes"""
        new_time_key = self.gossip_counter
        if len(self.data) > 0:
            latest_entry = max(self.data.keys(), key=int)
            latest_data = self.data[latest_entry]
            self.data[new_time_key] = latest_data
        else:
            self.data[new_time_key] = {}
        self.data[new_time_key][self.ip + ':' + self.port] = collect_system_metrics()
        random_nodes = self.get_random_nodes(self.node_list, target_count)

        for n in random_nodes:
            self.send_to_node(n, new_time_key)

    def update_failure_data(self, new_time_key, n):
        """Update failure data for a node"""
        if self.ip + ':' + self.port not in self.data[new_time_key].get(n["ip"] + ':' + n["port"], {}).get("hbState",
                                                                                                           {}).get(
            "failureList", []):
            self.data[new_time_key][n["ip"] + ':' + n["port"]]["hbState"]["failureList"].append(
                self.ip + ':' + self.port)
            f_count = self.data[new_time_key].get(n["ip"] + ':' + n["port"], {}).get("hbState", {}).get("failureCount",
                                                                                                        0) + 1
            if f_count >= 3:
                self.delete_node_from_nodelist(n["ip"] + ':' + n["port"])
                self.data[new_time_key][n["ip"] + ':' + n["port"]]["hbState"]["nodeAlive"] = False

    def delete_node_from_nodelist(self, key_to_delete):
        """Remove a failed node from the node list"""
        self.node_list.pop(key_to_delete)

    def prepare_requested_data(self, time_key, requested_keys):
        """Prepare requested data for transmission"""
        requested_data = {}
        for key in requested_keys:
            requested_data[key] = self.data[time_key][key]
        return requested_data

    def reset_failure_data(self, new_time_key, ip_key):
        """Reset failure data for a recovered node"""
        if ip_key in self.data[new_time_key]:
            self.data[new_time_key][ip_key]["hbState"]["failureCount"] = 0
            self.data[new_time_key][ip_key]["hbState"]["nodeAlive"] = True
            self.data[new_time_key][ip_key]["hbState"]["failureList"] = []
        else:
            self.data[new_time_key].setdefault(ip_key, {}).setdefault("hbState", {})[
                "failureCount"] = 0
            self.data[new_time_key].setdefault(ip_key, {}).setdefault("hbState", {})[
                "failureList"] = []
            self.data[new_time_key][ip_key]["hbState"]["nodeAlive"] = True

    def update_own_data(self, updates, new_time_key):
        """Update own data with received updates"""
        for u_key in updates:
            self.data_flow_per_round.setdefault(self.cycle, {})
            if u_key in self.data[new_time_key]:
                self.data_flow_per_round[self.cycle].setdefault('fd', 0)
                self.data_flow_per_round[self.cycle]['fd'] += 1
            else:
                self.data_flow_per_round[self.cycle].setdefault('nd', 0)
                self.data_flow_per_round[self.cycle].setdefault('fd', 0)
                self.data_flow_per_round[self.cycle]['nd'] += 1
                self.data_flow_per_round[self.cycle]['fd'] += 1
            self.data[new_time_key][u_key] = updates[u_key]

    def send_to_node(self, n, new_time_key):
        """Send data to a specific node"""
        data = self.prepare_metadata_and_own_fresh_data(new_time_key)
        try:
            r_metadata_and_updated = requests.post(
                'http://' + n["ip"] + ':' + '5000' + '/receive_metadata',
                json=data)

            requested_keys = r_metadata_and_updated.json()['requested_keys']
            requested_data = self.prepare_requested_data(new_time_key, requested_keys)
            response = requests.get(
                'http://' + n["ip"] + ':' + '5000' + '/receive_message?inc_round={}'.format(self.cycle),
                json=requested_data)
            self.update_own_data(r_metadata_and_updated.json()['updates'], new_time_key)
            if response.status_code == 500:
                self.update_failure_data(new_time_key, n)
            else:
                self.reset_failure_data(new_time_key, n["ip"] + ':' + n["port"])
        except Exception as e:
            logging.error("Error while sending message to node {}: {}".format(n, e))

    def set_params(self, ip, port, cycle, node_list, data, is_alive, gossip_counter, failure_counter,
                   monitoring_address, database_address, is_send_data_back, client_thread, counter_thread, 
                   data_flow_per_round, push_mode, client_port):
        """Set node parameters"""
        self.ip = ip
        self.port = port
        self.monitoring_address = monitoring_address
        self.database_address = database_address
        self.cycle = cycle
        self.node_list = node_list
        self.data = data
        self.is_alive = is_alive
        self.gossip_counter = gossip_counter
        self.failure_counter = failure_counter
        self.client_thread = client_thread
        self.counter_thread = counter_thread
        self.data_flow_per_round = data_flow_per_round
        self.is_send_data_back = is_send_data_back
        self.push_mode = push_mode
        self.client_port = client_port

    def get_random_nodes(self, node_list, target_count):
        """Get random nodes from the node list for communication"""
        new_node_list = []
        for node in node_list:
            if self.ip == node['ip']:
                continue
            new_node_list.append(node)
        random_os_data = os.urandom(16)
        seed = int.from_bytes(random_os_data, byteorder="big")
        random.seed(seed)
        return random.sample(new_node_list, target_count)

    def push_latest_data_and_delete_after_push(self):
        """Push latest data to monitoring system and clean up old data"""
        if self.data:
            latest_time_key = max(self.data.keys())
            latest_data = self.data[latest_time_key]
            to_send = self.data
            self.data = {latest_time_key: latest_data}
            to_push = {k: v for k, v in to_send.items() if k != latest_time_key}
            self.session_to_monitoring.post(
                'http://{}:{}/push_data_to_database?ip={}&port={}&round={}'.format(
                    self.monitoring_address, self.client_port, self.ip,
                    self.port, self.cycle), json=to_push)

    def get_filtered_data_by_priority(self, full_data):
        """Filter metrics based on priority and round number"""
        if not hasattr(self, 'metric_last_sent'):
            self.metric_last_sent = {}
        
        filtered_data = full_data.copy()
        
        # Don't filter if it's the first time sending data
        if self.cycle <= 1:
            for metric in METRIC_PRIORITIES:
                self.metric_last_sent[metric] = self.cycle
            return filtered_data
        
        # Filter app state metrics based on priority
        if "appState" in filtered_data:
            app_state = filtered_data["appState"].copy()
            for metric, priority in METRIC_PRIORITIES.items():
                last_sent = self.metric_last_sent.get(metric, 0)
                if (self.cycle - last_sent) < priority:
                    # Remove metrics that don't need to be sent this round
                    if metric in app_state:
                        app_state[metric] = "not_updated"
                else:
                    # Update last sent time for metrics being sent
                    self.metric_last_sent[metric] = self.cycle
            
            filtered_data["appState"] = app_state
        
        return filtered_data
