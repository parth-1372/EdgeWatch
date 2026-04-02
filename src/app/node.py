import time
import psutil
import requests
from singleton import Singleton
import logging
import secrets
from utility import mk_digest

logger = logging.getLogger("demon.metrics")

# Priority levels
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


def get_new_data():
    """Collect current resource metrics and apply VoI priority filtering.
    
    Returns a gossip-ready data dict. Metrics that don't pass the priority/delta
    filter are replaced with the sentinel string "not_updated" so peers know to
    keep their cached value instead of overwriting with a stale one.
    """
    node = Node.instance()

    # ---------------------------------------------------------------------------
    # Calculate Bandwidth (Mbps) — using instance state so resets survive
    # a /reset_node or /start_node call cleanly.
    # ---------------------------------------------------------------------------
    current_network_bytes = (
        psutil.net_io_counters().bytes_recv
        + psutil.net_io_counters().bytes_sent
    )
    current_time = time.time()

    if node.last_network_bytes == 0:
        # First call — initialise baseline, report 0 Mbps
        node.last_network_bytes = current_network_bytes
        node.last_network_time = current_time
        bandwidth_mbps = 0.0
    else:
        delta_bytes = current_network_bytes - node.last_network_bytes
        delta_time = current_time - node.last_network_time

        if delta_time > 0:
            bandwidth_mbps = (delta_bytes * 8) / (delta_time * 1024 * 1024)
        else:
            bandwidth_mbps = 0.0

        node.last_network_bytes = current_network_bytes
        node.last_network_time = current_time

    # Calculate Storage (Usage %)
    storage_percent = psutil.disk_usage('/').percent

    # Get process-specific CPU/memory (non-blocking cpu_percent avoids stalling
    # the gossip thread; the first call returns 0.0 which is acceptable).
    cpu_usage = node.node_process.cpu_percent(interval=None)
    memory_usage = node.node_process.memory_percent()

    current_metrics = {
        "cpu": cpu_usage,
        "memory": memory_usage,
        "network": bandwidth_mbps,
        "storage": storage_percent,
    }

    # Apply VoI priority + delta filtering
    metrics_to_send = {}
    metrics_filtered = {}

    for metric, value in current_metrics.items():
        if should_send_metric(node, metric, value):
            metrics_to_send[metric] = value
        else:
            metrics_filtered[metric] = value

    # Build appState — omitted metrics stay as "not_updated"
    app_state = {}
    for metric in metrics_to_send:
        app_state[metric] = str(metrics_to_send[metric])

    # Round-level statistics
    node.data_flow_per_round.setdefault(node.cycle, {})
    node.data_flow_per_round[node.cycle]['metrics_sent'] = len(metrics_to_send)
    node.data_flow_per_round[node.cycle]['metrics_filtered'] = len(metrics_filtered)

    metric_flags = {metric: (metric in metrics_to_send) for metric in current_metrics}

    data = {
        "counter": "{}".format(node.gossip_counter),
        "cycle": "{}".format(node.cycle),
        "digest": "",
        "nodeState": {
            "id": "",
            "ip": "{}".format(node.ip),
            "port": "{}".format(node.port),
        },
        "hbState": {
            "timestamp": "{}".format(time.time()),
            "failureCount": node.failure_counter,
            "failureList": node.failure_list,
            "nodeAlive": node.is_alive,
        },
        "appState": app_state,
        "nfState": {},
        "metric_sent_flags": metric_flags,
    }

    digest = mk_digest(data)
    data["digest"] = digest

    return data


def should_send_metric(node, metric, value):
    """Evaluate VoI priority + delta rule for a single metric.
    
    Uses per-node instance state (node.last_metric_values, node.last_metric_sent_round)
    so that state is properly reset when the node is re-initialised.
    """
    if metric not in node.last_metric_values:
        node.last_metric_values[metric] = value
        node.last_metric_sent_round[metric] = 0
        return True  # Always send the first reading

    priority = METRIC_PRIORITIES.get(metric, PRIORITY_HIGH)
    rounds_since_sent = node.cycle - node.last_metric_sent_round.get(metric, 0)

    # Delta calculation
    prev = node.last_metric_values[metric]
    if isinstance(value, (int, float)) and isinstance(prev, (int, float)) and prev != 0:
        if metric in ("network", "storage"):
            delta_percent = abs(value - prev) / max(value, prev) * 100
        else:
            delta_percent = abs(value - prev)
    else:
        delta_percent = float('inf')

    should_send = False

    if priority == PRIORITY_HIGH:
        should_send = True
    elif rounds_since_sent >= priority:
        should_send = True
    elif delta_percent >= METRIC_DELTAS.get(metric, 0):
        should_send = True

    if should_send:
        node.last_metric_sent_round[metric] = node.cycle

    node.last_metric_values[metric] = value

    logger.debug(
        "METRIC_PRIORITY: metric=%s, value=%.2f, priority=%d, "
        "delta=%.2f%%, rounds_since_sent=%d, decision=%s",
        metric, value, priority, delta_percent,
        rounds_since_sent, 'SEND' if should_send else 'SKIP',
    )

    return should_send


@Singleton
class Node:
    """Singleton gossip node — holds all per-node runtime state.
    
    All metric-tracking fields are instance attributes so they reset cleanly
    when set_params() is called for a new experiment run (fixes the stale-globals
    bug reported in node.py where last_network_bytes etc. outlived the Node
    lifecycle and caused negative rounds_since_sent).
    """

    def __init__(self):
        self.ip = None
        self.port = None
        self.cycle = None
        self.node_list = None
        self.data = None
        self.data_flow_per_round = None
        self.is_alive = None
        self.gossip_counter = None
        self.failure_counter = None
        self.failure_list = []
        self.monitoring_address = None
        self.database_address = None
        self.client_thread = None
        self.counter_thread = None
        self.push_mode = None
        self.is_send_data_back = None
        self.metric_last_sent = {}

        # VoI metric tracking — stored as instance attrs so they reset on re-init
        self.last_metric_values = {}
        self.last_metric_sent_round = {}
        self.last_network_bytes = 0
        self.last_network_time = time.time()
        self.node_process = psutil.Process()

        # Quiesce event — set by the gossip loop when it exits, used by /terminate
        self.quiesced_event = None

    def set_params(self, ip, port, cycle, node_list, data, is_alive, gossip_counter,
                   failure_counter, monitoring_address, database_address,
                   is_send_data_back, client_thread, counter_thread,
                   data_flow_per_round, push_mode, client_port):
        """(Re-)initialise node state for a new experiment run.
        
        Resets all per-lifecycle fields including metric tracking state so that
        VoI filtering behaves correctly from round 0 of each new run.
        """
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

        # Reset metric tracking state — prevents stale baselines leaking across runs
        self.last_metric_values = {}
        self.last_metric_sent_round = {}
        self.last_network_bytes = 0
        self.last_network_time = time.time()
        self.node_process = psutil.Process()

        # Fresh quiesce signal for this run
        import threading
        self.quiesced_event = threading.Event()

    def get_random_nodes(self, node_list, target_count):
        """Return a random sample of peers, excluding self."""
        filtered_nodes = [node for node in node_list if node['ip'] != self.ip]
        return secrets.SystemRandom().sample(filtered_nodes, target_count)

    def start_gossip_counter(self):
        """Background thread: increments gossip_counter once per second."""
        while self.is_alive:
            self.gossip_counter += 1
            time.sleep(1)

    def start_gossiping(self, target_count, gossip_rate):
        """Main gossip loop — runs until is_alive is set False."""
        print("Starting gossiping with target count: {} and gossip rate: {} and length of node list: {}".format(
            target_count, gossip_rate, len(self.node_list)),
            flush=True)
        try:
            while self.is_alive:
                if self.push_mode == "1":
                    print("Pushing data", flush=True)
                    if self.cycle % 10 == 0 and self.cycle != 0:
                        self.push_latest_data_and_delete_after_push()
                self.cycle += 1
                self.transmit(target_count)
                time.sleep(gossip_rate)
        finally:
            # Signal /terminate that the gossip loop has quiesced
            if self.quiesced_event is not None:
                self.quiesced_event.set()

    def transmit(self, target_count):
        """Build and send current state to target_count randomly selected peers."""
        new_time_key = self.gossip_counter

        if self.data:
            latest_entry = max(self.data.keys(), key=int)
            latest_data = self.data[latest_entry].copy()
        else:
            latest_data = {}

        latest_data[f"{self.ip}:{self.port}"] = get_new_data()
        self.data[new_time_key] = latest_data

        random_nodes = self.get_random_nodes(self.node_list, target_count)

        for node in random_nodes:
            self.send_to_node(node, new_time_key)

    def prepare_metadata_and_own_fresh_data(self, time_key):
        """Package this node's own fresh data + peer counters for metadata exchange."""
        own_key = f"{self.ip}:{self.port}"
        time_data = self.data[time_key]
        own_recent_data = time_data[own_key]

        filtered_own_data = self.get_filtered_data_by_priority(own_recent_data)

        metadata = {
            key: node_data['counter']
            for key, node_data in time_data.items()
            if key != own_key and 'counter' in node_data
        }

        return {'metadata': metadata, own_key: filtered_own_data}

    def prepare_requested_data(self, time_key, requested_keys):
        """Return the subset of stored data requested by a peer."""
        requested_data = {}
        for key in requested_keys:
            requested_data[key] = self.data[time_key][key]
        return requested_data

    def update_own_data(self, updates, new_time_key):
        """Merge incoming peer updates into local data store."""
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

    def get_filtered_data_by_priority(self, full_data):
        """Apply VoI priority filtering to outgoing gossip data."""
        filtered_data = full_data.copy()
        # First cycle — always send everything to bootstrap the network
        if self.cycle <= 1:
            for metric in METRIC_PRIORITIES:
                self.metric_last_sent[metric] = self.cycle
            return filtered_data

        if "appState" in filtered_data:
            app_state = filtered_data["appState"].copy()
            for metric, priority in METRIC_PRIORITIES.items():
                last_sent = self.metric_last_sent.get(metric, 0)
                if (self.cycle - last_sent) < priority:
                    if metric in app_state:
                        app_state[metric] = "not_updated"
                else:
                    self.metric_last_sent[metric] = self.cycle

            filtered_data["appState"] = app_state

        return filtered_data

    def push_latest_data_and_delete_after_push(self):
        """Push accumulated data to the monitoring server, keeping only the latest entry."""
        if self.data:
            latest_time_key = max(self.data.keys())
            latest_data = self.data[latest_time_key]
            to_send = self.data
            self.data = {latest_time_key: latest_data}
            to_push = {k: v for k, v in to_send.items() if k != latest_time_key}
            self.session_to_monitoring.post(
                'http://{}:{}/push_data_to_database?ip={}&port={}&round={}'.format(
                    self.monitoring_address, self.client_port,
                    self.ip, self.port, self.cycle
                ),
                json=to_push,
            )

    def send_to_node(self, n, new_time_key):
        """Push-pull gossip exchange with peer node n."""
        data = self.prepare_metadata_and_own_fresh_data(new_time_key)
        try:
            r_metadata_and_updated = self.gossip_session.post(
                'http://' + n["ip"] + ':' + '5000' + '/receive_metadata',
                json=data, timeout=5)

            requested_keys = r_metadata_and_updated.json()['requested_keys']
            requested_data = self.prepare_requested_data(new_time_key, requested_keys)
            response = self.gossip_session.get(
                'http://' + n["ip"] + ':' + '5000' + '/receive_message?inc_round={}'.format(self.cycle),
                json=requested_data, timeout=5)
            self.update_own_data(r_metadata_and_updated.json()['updates'], new_time_key)
            if response.status_code == 500:
                self.update_failure_data(new_time_key, n)
            else:
                self.reset_failure_data(new_time_key, n["ip"] + ':' + n["port"])
        except Exception as e:
            logging.error("Error while sending message to node {}: {}".format(n, e))

    def update_failure_data(self, new_time_key, n):
        """Record a failed contact attempt against peer n (heartbeat / 3-strike)."""
        peer_key = n["ip"] + ':' + n["port"]
        own_key = self.ip + ':' + self.port
        if own_key not in self.data[new_time_key].get(peer_key, {}).get("hbState", {}).get("failureList", []):
            self.data[new_time_key][peer_key]["hbState"]["failureList"].append(own_key)
            f_count = self.data[new_time_key].get(peer_key, {}).get("hbState", {}).get("failureCount", 0) + 1
            if f_count >= 3:
                self.delete_node_from_nodelist(peer_key)
                self.data[new_time_key][peer_key]["hbState"]["nodeAlive"] = False

    def delete_node_from_nodelist(self, key_to_delete):
        """Remove a node from the gossip peer list (post 3 strikes)."""
        self.node_list = [n for n in self.node_list
                          if n["ip"] + ":" + n["port"] != key_to_delete]

    def reset_failure_data(self, new_time_key, ip_key):
        """Clear failure state for a peer that responded successfully."""
        if ip_key in self.data[new_time_key]:
            self.data[new_time_key][ip_key]["hbState"]["failureCount"] = 0
            self.data[new_time_key][ip_key]["hbState"]["nodeAlive"] = True
            self.data[new_time_key][ip_key]["hbState"]["failureList"] = []
        else:
            self.data[new_time_key].setdefault(ip_key, {}).setdefault("hbState", {})["failureCount"] = 0
            self.data[new_time_key].setdefault(ip_key, {}).setdefault("hbState", {})["failureList"] = []
            self.data[new_time_key][ip_key]["hbState"]["nodeAlive"] = True

    # Sessions — shared across all calls for connection re-use
    session_to_monitoring = requests.Session()
    gossip_session = requests.Session()
