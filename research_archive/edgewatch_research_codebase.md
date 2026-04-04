# EdgeWatch Core Codebase Reference

This document provides a complete sequential trace of the main codebase logic necessary to execute distributed Value-of-Information (VoI) experiments on EdgeWatch.

The logic flows roughly top-down:
1. Orchestration and initialization.
2. Node HTTP APIs and core gossip mechanics.
3. Quorum validations and consistency mechanisms.
4. Database recording and visual analytics tools.

---

### 1. `experiments/monitoring.py`
This is the main orchestrator and entry point for running the EdgeWatch experiments. It controls the lifecycle of the distributed system by spawning Docker containers, triggering experiments with specific configurations, tracking global network convergence, inserting run outcomes into the SQLite database, and providing a bridge to the dashboard for live metrics visualization.

```python
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import concurrent.futures
import configparser
import json
import random
import sqlite3
import time
import docker
import socket
import requests
import traceback
import queue
import threading
from flask import Flask, request
from joblib import Parallel, delayed
import connector_db as dbConnector
from sqlite3 import Connection
from src import query_client

session = requests.Session()

monitoring_priomon = Flask(__name__)
parser = configparser.ConfigParser()
parser.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
try:
    docker_client = docker.client.from_env()
except Exception as e:
    print("Error docker: {}".format(e))
    print("trace: {}".format(traceback.format_exc()))
    exit(1)
experiment = None
# protects concurrent reads/writes to run state from Flask threads
run_lock = threading.Lock()

def execute_queries_from_queue():
    """Dedicated SQLite writer thread — drains the query_queue in batches.

    Batching (commit every N items or when the queue drains temporarily) amortises
    the fsync cost of WAL-mode writes without losing data.  On failure the
    transaction is rolled back, the cursor is recreated (a stale cursor after
    rollback can produce silent failures in SQLite's Python driver), and the
    failed batch is discarded — individual items are marked task_done so
    join() callers are never left hanging.
    """
    conn = sqlite3.connect('priomonDB.db', check_same_thread=False)
    cursor = conn.cursor()

    batch_size = 50
    pending_items = []

    while True:
        query_data = None
        try:
            query_data = experiment.query_queue.get()
            if query_data is None:
                # Poison pill — flush and exit
                if pending_items:
                    conn.commit()
                    for _ in pending_items:
                        experiment.query_queue.task_done()
                    pending_items = []
                experiment.query_queue.task_done() # Mark poison-pill as done
                break

            query, parameters = query_data
            cursor.execute(query, parameters)
            pending_items.append(query_data)

            # Commit when batch is full or queue is temporarily empty
            if len(pending_items) >= batch_size or experiment.query_queue.empty():
                conn.commit()
                for _ in pending_items:
                    experiment.query_queue.task_done()
                pending_items = []

        except sqlite3.Error as e:
            print("Error db batch: {}".format(e))
            print("trace: {}".format(traceback.format_exc()))
            try:
                conn.rollback()
            except sqlite3.Error as e:
                print("Error rollback db batch: {}".format(e))
                print("trace: {}".format(traceback.format_exc()))

            # Recreate the cursor — a cursor after rollback can be in an
            # undefined state in SQLite's Python driver, leading to silent
            # failures on the very next execute() call.
            try:
                cursor = conn.cursor()
            except sqlite3.Error as e:
                print("Error recreate cursor db batch: {}".format(e))
                print("trace: {}".format(traceback.format_exc()))

            # Mark every pending item (already dequeued) as done so join()
            # callers are never left hanging.
            for _ in pending_items:
                experiment.query_queue.task_done()
            pending_items = []

            # query_data was dequeued with .get() but not yet added to
            # pending_items — mark it done only if that's the case.
            if query_data is not None:
                experiment.query_queue.task_done()

            continue

def get_target_count(node_count, target_count_range):
    new_range = []
    for i in target_count_range:
        if i <= node_count:
            new_range.append(i)
    return new_range

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def make_save_able_dic_from_run(run):
    save_able_dic = {"node_count": run.node_count, "target_count": run.target_count, "gossip_rate": run.gossip_rate,
                     "start_time": run.start_time, "convergence_time": run.convergence_time,
                     "convergence_message_count": run.convergence_message_count,
                     "convergence_round": run.convergence_round}
    return save_able_dic

def save_run_to_database(run):
    run.db_id = experiment.db.insert_into_run(experiment.db_id, run.run, run.node_count, run.gossip_rate,
                                              run.target_count)

def save_converged_run_to_database(run):
    experiment.db.insert_into_converged_run(run.db_id, run.convergence_round, run.convergence_message_count,
                                            run.convergence_time)

class Run:
    def __init__(self, node_count, gossip_rate, target_count, run, node_list=None, db_collection=None):
        self.db_id = -1
        self.data_entries_per_ip = {}
        self.node_list = node_list or []
        self.node_count = int(node_count)
        self.convergence_round = -1
        self.convergence_message_count = -1
        self.message_count = 0
        self.start_time = None
        self.convergence_time = None
        self.is_converged = False
        self.gossip_rate = float(gossip_rate)
        self.target_count = int(target_count)
        self.run = int(run)
        self.db_collection = db_collection
        self.max_round_is_reached = False
        self.ip_per_ic = {}
        self.stopped_nodes = {}
        self.manually_killed_count = 0  # Incremented when dashboard kills a node
        self.killed_node_keys = set()    # Set of "ip:port" manually killed

    def set_db_id(self, param):
        self.db_id = param

class Experiment:
    def __init__(self, node_count_range, gossip_rate_range, target_count_range, run_count, monitoring_address_ip,
                 is_send_data_back, push_mode):
        self.db_id = -1
        self.node_count_range = node_count_range
        self.gossip_rate_range = gossip_rate_range
        self.target_count_range = target_count_range
        self.run_count = run_count
        self.runs = []
        self.monitoring_address_ip = monitoring_address_ip
        self.db = dbConnector.PrioMonDB()
        self.query_queue = queue.Queue()
        self.query_thread = None
        self.is_send_data_back = is_send_data_back
        self.push_mode = push_mode
        self.NodeDB = dbConnector.NodeDB()

    def set_db_id(self, param):
        self.db_id = param

MAX_SPAWN_RETRIES = 5

def spawn_node(index, node_list, client, custom_network_name, retries=0):
    if retries >= MAX_SPAWN_RETRIES:
        print("Failed to spawn node {} after {} retries, giving up".format(index, MAX_SPAWN_RETRIES))
        return
    try:
        new_node = docker_client.containers.run("priomonv1", auto_remove=True, detach=True,
                                                network_mode=custom_network_name,
                                                ports={'5000': node_list[index]["port"]})
    except Exception as e:
        print("Node not spawned: {}".format(e))
        print("trace: {}".format(traceback.format_exc()))
        node_list[index]["port"] = get_free_port()
        spawn_node(index, node_list, client, custom_network_name, retries + 1)
    else:
        node_details = client.containers.get(new_node.id)
        node_list[index] = {"id": node_details.id,
                            "ip": node_details.attrs['NetworkSettings']['Networks']['test']['IPAddress'],
                            "port": node_details.attrs['NetworkSettings']['Ports']['5000/tcp'][0]['HostPort']}

def spawn_multiple_nodes(run):
    network_name = "test"
    from_index = 0
    if run.node_list is None:
        run.node_list = [None] * run.node_count
    elif len(run.node_list) == run.node_count:
        return  # Nodes are already spawned
    else:
        from_index = len(run.node_list)
        run.node_list = run.node_list + [None] * (run.node_count - len(run.node_list))
    client = docker.DockerClient()
    # TODO: free ports on i
    for i in range(from_index, run.node_count):
        run.node_list[i] = {}
        run.node_list[i]["port"] = get_free_port()
    Parallel(n_jobs=-1, prefer="threads")(
        delayed(spawn_node)(i, run.node_list, client, network_name) for i in range(from_index, run.node_count))

def nodes_are_ready(run):
    for i in range(0, run.node_count):
        if docker_client.containers.get(run.node_list[i]['id']).status != "running":
            return False
        run.node_list[i]["is_alive"] = True
    return True

def restart_node(docker_id):
    try:
        docker_client.containers.get(docker_id).restart()
    except Exception as e:
        print("An error occurred while restarting the container: {}".format(e))

def reset_node(ip, port, docker_id):
    try:
        time.sleep(random.uniform(0.01, 0.05))
        session.get("http://{}:{}/reset_node".format(ip, port), timeout=30)
    except Exception as e:
        print("An error occurred while sending the request: {}".format(e))
        restart_node(docker_id)

@monitoring_priomon.route('/delete_nodes', methods=['GET'])
def delete_all_nodes():
    to_remove = docker_client.containers.list(filters={"ancestor": "priomonv1"})
    for node in to_remove:
        node.remove(force=True)
    return "OK"

# not a route — called internally by the experiment loop, needs a run object
def restart_all_nodes(run):
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=run.node_count) as executor:
        for i in range(0, run.node_count):
            executor.submit(restart_node, run.node_list[i]["id"])
    print("Restart time: {}".format(time.time() - start), flush=True)

# def start_node(index, run, database_address, monitoring_address, ip):
#     to_send = {"node_list": run.node_list, "target_count": run.target_count, "gossip_rate": run.gossip_rate,
#                "database_address": database_address, "monitoring_address": monitoring_address,
#                "node_ip": run.node_list[index]["ip"], "is_send_data_back": experiment.is_send_data_back,
#                "push_mode": experiment.push_mode, "client_port": parser.get('PriomonParam', 'client_port')}
#     try:
#         time.sleep(0.01)
#         session.post("http://{}:{}/start_node".format(ip, run.node_list[index]["port"]), json=to_send)
#     except Exception as e:
#         print("Node not started: {}".format(e))
#         start_node(index, run, database_address, monitoring_address, ip)
def start_node(index, run, database_address, monitoring_address, ip, retries=0):
    if retries > 5:
        print(f"Giving up starting node {index} after 5 retries. It may have been killed.")
        return
    to_send = {"node_list": run.node_list, "target_count": run.target_count, "gossip_rate": run.gossip_rate,
               "database_address": database_address, "monitoring_address": monitoring_address,
               "node_ip": run.node_list[index]["ip"], "is_send_data_back": experiment.is_send_data_back,
               "push_mode": experiment.push_mode, "client_port": parser.get('PriomonParam', 'client_port')}
    try:
        time.sleep(0.01)
        session.post("http://{}:{}/start_node".format(ip, run.node_list[index]["port"]), json=to_send)
    except Exception as e:
        print(f"Node {index} not started: {e}. Retrying...")
        time.sleep(0.5)
        start_node(index, run, database_address, monitoring_address, ip, retries + 1)
def start_run(run, monitoring_address):
    database_address = parser.get('database', 'db_file')
    ip = parser.get('system_setting', 'docker_ip')
    run.start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=run.node_count) as executor:
        for i in range(0, run.node_count):
            executor.submit(start_node, i, run, database_address, monitoring_address, ip)

def reset_run_sync(run):
    ip = parser.get('system_setting', 'docker_ip')
    print("Resetting nodes", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=run.node_count) as executor:
        for i in range(0, run.node_count):
            executor.submit(reset_node, ip, run.node_list[i]["port"], run.node_list[i]["id"])

def prepare_run(run):
    spawn_multiple_nodes(run)
    while not nodes_are_ready(run):
        time.sleep(1)
    save_run_to_database(run)
    print("Run {} started".format(run.db_id), flush=True)

    # --- Notify dashboard of a new experiment run and its initial node set ---
    def _notify_run_start():
        try:
            nodes = []
            for node in run.node_list:
                if node and 'ip' in node and 'port' in node:
                    nodes.append({"ip": node['ip'], "port": node['port']})
            
            payload = {
                "node_count": run.node_count,
                "active_target": run.node_count,
                "nodes": nodes,
                "timestamp": time.time()
            }
            requests.post("http://localhost:5000/api/live-run-start", json=payload, timeout=2)
        except Exception:
            pass

    threading.Thread(target=_notify_run_start, daemon=True).start()
    # -------------------------------------------------------------------------
    
    time.sleep(10)

def check_if_all_nodes_are_reset(run):
    for node in run.node_list:
        if node["is_alive"]:
            return False
    return True

def stop_node_percentage(run, percent):
    print("stopping percentage of nodes: {}".format(percent))
    if percent == 0:
        return
    nodes_to_stop_count = int(len(run.node_list) * percent)
    indices = list(range(len(run.node_list)))
    random_indices_to_stop = random.sample(indices, nodes_to_stop_count)
    for i in random_indices_to_stop:
        try:
            container_to_stop = docker_client.containers.get(run.node_list[i]["id"])
            container_to_stop.stop()
            run.node_list[i]["is_alive"] = False
            run.stopped_nodes[i] = run.node_list[i]
        except Exception as e:
            print("An error occurred while stopping container: {}".format(e))
    print("{}% of nodes (n={}) are stopped".format(percent * 100, nodes_to_stop_count))
    return

def run_converged(run):
    if run.is_converged:
        return
    run.convergence_message_count = run.message_count
    # Guard against start_time race condition — should not happen after the fix,
    # but we protect here as a safety net.
    if run.start_time is not None:
        run.convergence_time = time.time() - run.start_time
    else:
        run.convergence_time = 0.0
    print("Convergence time: {}".format(run.convergence_time))
    print("Convergence message count: {}".format(run.convergence_message_count))
    run.is_converged = True


def check_convergence(run, data_stored_in_node):
    """
    Convergence is reached when every *alive* peer in the gossip snapshot
    holds an entry in this node's data store AND every entry has a counter.

    Key insight for chaos testing:
    When a node is killed, the survivors stop hearing from it and eventually
    delete it from their node_list (3-strike rule in node.py).  At that point,
    the killed node no longer appears in data_stored_in_node.  We count how
    many unique alive peers appear in the snapshot, and declare convergence
    when all of them agree on the same alive set.

    We also honour run.manually_killed_count so that the node_count target
    is immediately lowered as soon as the dashboard kills a node manually
    (before the 3-strike eviction propagates through the network).
    """
    if run.is_converged:
        return True

    # Count how many peers this reporter currently believes are alive
    alive_peers = {
        peer for peer, d in data_stored_in_node.items()
        if d.get("hbState", {}).get("nodeAlive", True)
    }

    # Subtract nodes that have been manually killed and registered with us
    expected_count = run.node_count - run.manually_killed_count
    if expected_count <= 0:
        return False  # Everyone is dead — nothing to declare

    # We need enough alive peers (>= expected survivors) AND all must have a counter
    if len(alive_peers) < expected_count:
        return False

    for peer in alive_peers:
        peer_data = data_stored_in_node.get(peer, {})
        if "counter" not in peer_data:
            return False

    run_converged(run)
    return True


def save_query_in_database(run, i, failure_percent, target_key, time_to_query, total_messages_for_query, success):
    experiment.db.save_query_in_database(run.db_id, run.node_count, i, failure_percent, time_to_query,
                                         total_messages_for_query, success)
    pass

def run_queries(run, query_count, failure_percent):
    docker_ip = parser.get('system_setting', 'docker_ip')
    quorum_size = 3
    for i in range(0, query_count):
        alive_nodes = [item for item in run.node_list if item.get("is_alive", False)]
        
        # Skip this query if there are no alive nodes
        if not alive_nodes:
            print("No alive nodes available for querying")
            continue
            
        # Select target node only from alive nodes
        target_node = random.choice(alive_nodes)
        target_key = target_node["ip"] + ":" + target_node["port"]
        
        try:
            start_time = time.time()
            total_messages_for_query, query_result = query_client.query(
                alive_nodes, quorum_size, target_node["ip"], target_node["port"], docker_ip
            )
            time_to_query = time.time() - start_time
            success = True
        except Exception as e:
            print(f"Query failed: {e}")
            time_to_query = time.time() - start_time
            total_messages_for_query = 0
            success = False
            
        save_query_in_database(run, i, failure_percent, target_key, time_to_query, 
                              total_messages_for_query, success)

def update_during_run(run):
    # TODO: stop percentage of nodes and check AoI etc. (update run.node_list or stop logic (convergence) if wanted)
    # before convergence do something
    while not run.is_converged:
        time.sleep(0.1)
    print(parser.get('PriomonParam', 'continue_after_convergence'))
    if parser.get('PriomonParam', 'continue_after_convergence') == "1":
        print("Convergence reached, continuing run")
        while not run.max_round_is_reached:
            time.sleep(0.1)
        print("Max round reached: stop now")
    print("should start queries now")
    if parser.get('system_setting', 'query_logic') == "1":
        print(parser.get('system_setting', 'failure_rate'))
        failure_ratio = float(parser.get('system_setting', 'failure_rate'))
        stop_node_percentage(run, failure_ratio)
        time.sleep(20)
        run_queries(run, query_count=100, failure_percent=failure_ratio)

connection_pool = sqlite3.connect("NodeStorage.db", check_same_thread=False, isolation_level=None)
# Schema Initialization for NodeStorage.db
with connection_pool:
    connection_pool.execute("CREATE TABLE IF NOT EXISTS unique_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT)")
    connection_pool.execute("CREATE TABLE IF NOT EXISTS data_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, node TEXT, round INTEGER, key TEXT, unique_entry_id INTEGER)")

database_lock = threading.Lock()

@monitoring_priomon.route('/push_data_to_database', methods=['POST'])
def push_data_to_database():
    client_ip = request.args.get('ip')
    client_port = request.args.get('port')
    client_round = request.args.get('round')
    data = request.get_json()
    node_key = client_ip + ":" + client_port

    # Acquire the lock
    with database_lock:
        # Use a connection from the pool
        connection: Connection = connection_pool
        cursor = connection.cursor()

        for r, va in data.items():
            for k, j in va.items():
                v = json.dumps(j)
                cursor.execute('SELECT id FROM unique_entries WHERE key=? AND value=?', (k, v))
                existing_entry = cursor.fetchone()
                if existing_entry:
                    unique_entry_id = existing_entry[0]
                else:
                    cursor.execute('INSERT INTO unique_entries (key, value) VALUES (?, ?)', (k, v))
                    unique_entry_id = cursor.lastrowid

                cursor.execute('INSERT INTO data_entries (node, round, key, unique_entry_id) VALUES (?, ?, ?, ?)',
                               (node_key, client_round, k, unique_entry_id))
        connection_pool.commit()

    return "OK"

@monitoring_priomon.route('/notify_node_killed', methods=['POST'])
def notify_node_killed():
    """
    Called by the dashboard Chaos Engine after a soft-kill HTTP request
    succeeds.  We immediately lower the convergence target so the remaining
    nodes can declare convergence without waiting for the 3-strike timeout.
    """
    data = request.get_json(silent=True) or {}
    killed_ip = data.get("ip", "")
    with run_lock:
        if experiment and experiment.runs:
            run = experiment.runs[-1]
            run.manually_killed_count += 1
            # Erase the killed node from the gossip snapshot so the next
            # convergence check doesn't wait for its data any more.
            killed_key = data.get("ip", "") + ":" + str(data.get("port", ""))
            run.killed_node_keys.add(killed_key)
            run.data_entries_per_ip.pop(killed_key, None)
            print("[Chaos] Node {} manually killed. New target: {}/{}".format(
                killed_ip, run.node_count - run.manually_killed_count, run.node_count))
    return "OK"


@monitoring_priomon.route('/receive_ic', methods=['GET'])
def update_ic():
    client_ip = request.args['ip']
    client_port = request.args['port']
    with run_lock:
        experiment.runs[-1].ip_per_ic[client_ip + ":" + client_port] = True
        if len(experiment.runs[-1].ip_per_ic) == experiment.runs[-1].node_count:
            run_converged(experiment.runs[-1])
    return "OK"

@monitoring_priomon.route('/receive_node_data', methods=['POST'])
def update_data_entries_per_ip():
    if not experiment:
        print("No experiment running, but a gossip node is trying to send data")
        return "NOK"
    client_ip = request.args['ip']
    client_port = request.args['port']
    round = request.args['round']
    inc = request.get_json()
    data_stored_in_node = inc["data"]
    data_flow_per_round = inc["data_flow_per_round"]

    nd = data_flow_per_round.setdefault('nd', 0)
    fd = data_flow_per_round.setdefault('fd', 0)
    rm = data_flow_per_round.setdefault('rm', 0)

    ic = len(data_stored_in_node)
    bytes_of_data = len(json.dumps(data_stored_in_node).encode('utf-8'))
    with run_lock:
        experiment.runs[-1].convergence_round = max(experiment.runs[-1].convergence_round, int(round))
        experiment.runs[-1].message_count += 1
        experiment.runs[-1].data_entries_per_ip[client_ip + ":" + client_port] = data_stored_in_node
        check_convergence(experiment.runs[-1], data_stored_in_node)  # <-- FIX: Passed the data_stored_in_node variable
        if int(round) >= 80:
            run_converged(experiment.runs[-1])
            experiment.runs[-1].max_round_is_reached = True

    if not experiment.runs[-1].is_converged:
        current_node_count = int(experiment.runs[-1].node_count)
        if int(nd) > current_node_count:
            nd = current_node_count
        if int(fd) > current_node_count:
            fd = current_node_count
        delete_parameters = (experiment.runs[-1].db_id, client_ip, client_port, round)
        insert_parameters = (experiment.runs[-1].db_id, client_ip, client_port, round, nd, fd, rm, ic, bytes_of_data)
        experiment.query_queue.put(
            ("DELETE FROM round_of_node WHERE run_id = ? AND ip = ? AND port = ? AND round = ?", delete_parameters))
        experiment.query_queue.put((
                                   "INSERT INTO round_of_node (run_id, ip, port, round, nd, fd, rm, ic, bytes_of_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   insert_parameters))
    
    # Extract metrics statistics if available
    metrics_sent = data_flow_per_round.get('metrics_sent', 0)
    metrics_filtered = data_flow_per_round.get('metrics_filtered', 0)
    
    # Store metrics statistics
    if metrics_sent > 0 or metrics_filtered > 0:
        metrics_params = (experiment.runs[-1].db_id, client_ip, client_port, round, 
                         metrics_sent, metrics_filtered, time.time())
        experiment.query_queue.put((
            "INSERT INTO round_metrics_stats (run_id, node_ip, node_port, round, metrics_sent, metrics_filtered, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            metrics_params))
    
    # Store detailed per-metric transmission data
    if client_ip + ":" + client_port in data_stored_in_node:
        node_data = data_stored_in_node[client_ip + ":" + client_port]
        if 'metric_sent_flags' in node_data:
            timestamp = time.time()
            for metric_type, was_sent in node_data['metric_sent_flags'].items():
                # Get metric value if available
                metric_value = None
                if 'appState' in node_data and metric_type in node_data['appState']:
                    try:
                        metric_value = float(node_data['appState'][metric_type])
                    except (ValueError, TypeError):
                        pass
            
                # Queue the database insert
                metric_params = (experiment.runs[-1].db_id, client_ip, client_port, round, 
                                metric_type, 1 if was_sent else 0, metric_value, timestamp)
                experiment.query_queue.put((
                    "INSERT INTO metric_transmissions (run_id, node_ip, node_port, round, metric_type, was_sent, metric_value, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    metric_params))

    # Capture a local reference to the current run object to avoid reading
    # the state of a "next" run if the orchestrator moves on while the 
    # thread below is still executing.
    current_run = experiment.runs[-1]

    # --- Forward live metrics to the Express dashboard backend (non-blocking) ---
    def _forward_to_dashboard():
        try:
            peer_status = {}
            for peer, p_data in data_stored_in_node.items():
                if "hbState" in p_data:
                    peer_status[peer] = {
                        "isAlive": p_data["hbState"].get("nodeAlive", True),
                        "failCount": p_data["hbState"].get("failureCount", 0)
                    }
                else:
                    peer_status[peer] = {"isAlive": True, "failCount": 0}

            # Extract THIS node's own metrics from the gossip snapshot
            # so the dashboard Inspector can show real values.
            sender_key = client_ip + ":" + client_port
            sender_entry = data_stored_in_node.get(sender_key, {})
            app_state = sender_entry.get("appState", {})

            # FORCE-FILTER: Remove nodes that we know are manually killed
            # (Gossip survivors might still think they are alive for 3 rounds)
            filtered_data = {k: v for k, v in data_stored_in_node.items() if k not in current_run.killed_node_keys}

            # Calculate active_ic (only count peers that are alive and not manually killed)
            active_ic = sum(1 for p, d in filtered_data.items() if d.get("hbState", {}).get("nodeAlive", True))

            # Update nd to match the filtered reality
            filtered_nd = len(filtered_data)

            payload = {
                "ip": client_ip,
                "port": client_port,
                "round": round,
                "ic": active_ic,
                "nd": filtered_nd,
                "fd": fd,
                "rm": rm,
                "bytes_of_data": bytes_of_data,
                "node_count": current_run.node_count,
                "active_target": current_run.node_count - current_run.manually_killed_count,
                "message_count": current_run.message_count,
                "is_converged": current_run.is_converged,
                "data_stored_in_node": list(filtered_data.keys()),
                "peer_status": peer_status,
                # Top-level metric fields for the dashboard Inspector
                "cpu":     app_state.get("cpu",     "not_updated"),
                "memory":  app_state.get("memory",  "not_updated"),
                "network": app_state.get("network", "not_updated"),
                "storage": app_state.get("storage", "not_updated"),
            }
            requests.post("http://localhost:5000/api/live-metrics", json=payload, timeout=2)
        except Exception:
            pass  # dashboard may not be running; never block the experiment

    threading.Thread(target=_forward_to_dashboard, daemon=True).start()
    # ---------------------------------------------------------------------------

    return "OK"

def generate_run(node_count, gossip_rate, target_count, run_count):
    if experiment.runs:
        return Run(node_count, gossip_rate, target_count, run_count, node_list=experiment.runs[-1].node_list)
    return Run(node_count, gossip_rate, target_count, run_count)

def ensure_list(val):
    if isinstance(val, str):
        try:
            # If it's a string like "[1,2,3]", parse it
            loaded = json.loads(val)
            # If the result is still a string (double encoded), go one level deeper
            if isinstance(loaded, str):
                return json.loads(loaded)
            return loaded
        except:
            # Fallback for simple values
            return [val]
    return val if isinstance(val, list) else [val]

def prepare_experiment(server_ip):
    global experiment
    
    # Reload the configuration file to pick up any changes from the dashboard
    parser.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
    
    # Robustly parse ranges from the config file
    def get_range(section, key):
        raw = parser.get(section, key)
        return ensure_list(raw)

    node_range = get_range('PriomonParam', 'node_range')
    gossip_rate_range = get_range('PriomonParam', 'gossip_rate_range')
    target_count_range = get_range('PriomonParam', 'target_count_range')
    runs = int(parser.get('PriomonParam', 'runs'))

    experiment = Experiment(node_range,
                            gossip_rate_range,
                            target_count_range,
                            runs,
                            server_ip,
                            parser.get('system_setting', 'is_send_data_back'),
                            parser.get('PriomonParam', 'push_mode'))
    experiment.set_db_id(experiment.db.insert_into_experiment(time.time()))
    experiment.query_thread = threading.Thread(target=execute_queries_from_queue)
    experiment.query_thread.start()

def print_experiment():
    experiment.query_queue.put(None)
    experiment.query_thread.join()
    for run in experiment.runs:
        print("Run {}, converged after {} messages and {} seconds".format(run.node_count, run.convergence_message_count,
                                                                          run.convergence_time))

@monitoring_priomon.route('/start', methods=['GET', 'POST'])
def start_priomon():
    server_ip = socket.gethostbyname(socket.gethostname())
    print("Server IP: {}".format(server_ip))
    prepare_experiment(server_ip)
    for node_count in experiment.node_count_range:
        new_target_count_range = get_target_count(node_count, experiment.target_count_range)
        for target_count in new_target_count_range:
            for gossip_rate in experiment.gossip_rate_range:
                for run_count in range(0, experiment.run_count):
                    print("Preparing run with {} nodes, {} gossip rate, {} target count and {} run count".format(
                        node_count, gossip_rate, target_count, run_count))
                    run = generate_run(node_count, gossip_rate, target_count, run_count)  # db_collection=collection)
                    experiment.runs.append(run)
                    prepare_run(run)
                    print("Run {} prepared, with {} nodes online".format(run.run, len(run.node_list)))
                    start_run(run, experiment.monitoring_address_ip)
                    update_during_run(run)
                    save_converged_run_to_database(run)
                    reset_run_sync(run)
    print_experiment()
    delete_all_nodes()
    return "OK - Experiment finished"

def create_and_start_priomon_node(node_number, node_list, target_count, gossip_rate):    
    # metric priority configuration is currently handled directly in the spawned nodes
    pass
if __name__ == "__main__":
    monitoring_priomon.run(host='0.0.0.0', port=parser.getint('PriomonParam', 'client_port'), debug=False, threaded=True)
```

---

### 2. `src/app/priomon.py`
This is the lightweight Flask application running inside each distributed node object. It acts as the networking listener for the node. Here you'll find the endpoints used for the gossip protocol (exchanging metadata and messages) as well as the administrative endpoints the orchestrator invokes to setup, stop, or soft-kill the node.

```python
import time

from flask import Flask, request
from node import Node, METRIC_PRIORITIES, METRIC_DELTAS
import threading
import logging
import json

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
gossip = Flask(__name__)


@gossip.route('/receive_message', methods=['GET'])
def receive_message():
    if not Node.instance().is_alive:
        # reset_node()
        return "Dead Node", 500
    compare_and_update_node_data(request.get_json())
    return "OK"


@gossip.route('/metadata', methods=['GET'])
def get_metadata():
    if not Node.instance().is_alive:
        # reset_node()
        return "Dead Node", 500
    node = Node.instance()
    if not node.data:
        return json.dumps({})
    latest_entry = max(node.data.keys(), key=int)
    metadata = {}
    for key in node.data[latest_entry]:
        if 'counter' in node.data[latest_entry][key]:
            metadata[key] = {'counter': node.data[latest_entry][key]['counter'],
                             'digest': node.data[latest_entry][key]['digest']}
    return json.dumps(metadata)


def compare_node_data_with_metadata(data):
    # metadata form: {ip1: counter1, ip2: counter2, .....}
    # to_send = {'metadata': metadata, key:own_recent_data}
    node = Node.instance()
    metadata = data['metadata']
    sender_key = next(key for key in data if key != 'metadata')
    sender_data = data[sender_key]
    if len(node.data) == 0:
        # node doesnt store any data yet
        return metadata.keys()
    latest_entry = max(node.data.keys(), key=int)
    all_keys = set().union(node.data[latest_entry].keys(), metadata.keys())
    all_keys.discard(sender_key)
    node.data_flow_per_round.setdefault(node.cycle, {})
    if sender_key in node.data[latest_entry]:
        node.data_flow_per_round[node.cycle].setdefault('fd', 0)
        node.data_flow_per_round[node.cycle]['fd'] += 1
    else:
        node.data_flow_per_round[node.cycle].setdefault('nd', 0)
        node.data_flow_per_round[node.cycle].setdefault('fd', 0)
        node.data_flow_per_round[node.cycle]['nd'] += 1
        node.data_flow_per_round[node.cycle]['fd'] += 1

    node.data[latest_entry][sender_key] = sender_data

    # lists of ips who reclaim that this node is dead
    ips_to_update = []
    data_to_send = {}
    for key in all_keys:
        # both nodes store the data if IP
        if key in node.data[latest_entry] and key in metadata:
            # node doesnt store the key or counter of metadata > counter of noda.data
            if ('counter' not in node.data[latest_entry][key]) or (
                    float(metadata[key]) > float(node.data[latest_entry][key]['counter'])):
                ips_to_update.append(key)
            else:
                data_to_send[key] = node.data[latest_entry][key]
        # metadata doesnt store the data of IP
        elif key in node.data[latest_entry] and key not in metadata:
            data_to_send[key] = node.data[latest_entry][key]
        # node doesnt store the data of IP
        else:
            ips_to_update.append(key)
    requests_updates = {'requested_keys': ips_to_update, 'updates': data_to_send}
    return requests_updates


@gossip.route('/receive_metadata', methods=['POST'])
def receive_metadata():
    if not Node.instance().is_alive:
        # reset_node()
        return "Dead Node", 500
    data = compare_node_data_with_metadata(request.get_json())
    return data


@gossip.route('/reset_node')
def reset_node():
    node = Node.instance()
    node.is_alive = False
    node.client_thread.join()
    node.counter_thread.join()
    node.set_params(None, None, 0, None, {}, False, 0, 0, None, None,
                    is_send_data_back=None, client_thread=None,
                    counter_thread=None, data_flow_per_round={},
                    push_mode=0, client_port=None)
    return "OK"


@gossip.route('/stop_node')
def stop_node():
    node = Node.instance()
    node.is_alive = False
    node.client_thread.join()
    node.counter_thread.join()
    return "OK"


@gossip.route('/terminate', methods=['POST', 'GET'])
def terminate_node():
    """
    Soft-kill endpoint called by the Chaos Engine dashboard.
    Instantly sets is_alive=False so the node stops gossiping and returns
    500 to all peers on their next request, triggering their 3-strike
    failure detector — no docker stop required.
    """
    node = Node.instance()
    node.is_alive = False
    return "TERMINATED"


def compare_and_update_node_data(inc_data):
    node = Node.instance()
    new_time_key = node.gossip_counter
    latest_entry = max(node.data.keys(), key=int) if len(node.data) > 0 else new_time_key
    new_data = inc_data
    # new_data = inc_data['data']
    # new_node_list = inc_data['node_list']
    all_keys = set().union(node.data[latest_entry].keys(), new_data.keys())
    inc_round = int(request.args.get('inc_round'))
    # received messages ['rm'] per round
    node.data_flow_per_round.setdefault(node.cycle, {}).setdefault('rm', 0)
    node.data_flow_per_round[node.cycle]['rm'] += 1

    # lists of ips who reclaim that this node is dead
    list1 = []
    list2 = []
    for key in all_keys:
        # both nodes store the data if IP
        if key in node.data[latest_entry] and key in new_data:

            # Handle partial metric updates - preserve existing metrics if not in incoming data
            if 'appState' in new_data[key] and 'appState' in node.data[latest_entry][key]:
                # Get lists of metrics
                existing_metrics = set(node.data[latest_entry][key]['appState'].keys())
                incoming_metrics = set(new_data[key]['appState'].keys())
                
                # For any metric in existing but not in incoming, copy from existing
                for metric in existing_metrics - incoming_metrics:
                    new_data[key]['appState'][metric] = node.data[latest_entry][key]['appState'][metric]
            
            if 'metric_sent_flags' in new_data[key]:
                sent_count = sum(1 for v in new_data[key]['metric_sent_flags'].values() if v)
                filtered_count = sum(1 for v in new_data[key]['metric_sent_flags'].values() if not v)
        
                # Add to round statistics
                node.data_flow_per_round[node.cycle].setdefault('metrics_sent', 0)
                node.data_flow_per_round[node.cycle].setdefault('metrics_filtered', 0)
                node.data_flow_per_round[node.cycle]['metrics_sent'] += sent_count
                node.data_flow_per_round[node.cycle]['metrics_filtered'] += filtered_count
                
            list1 = node.data[latest_entry][key]["hbState"]["failureList"]
            list2 = new_data[key]["hbState"]["failureList"]
            if ('counter' in new_data[key] and 'counter' in node.data[latest_entry][key] \
                and float(new_data[key]['counter']) > float(node.data[latest_entry][key]['counter'])) or \
                    ('counter' in new_data[key] and 'counter' not in node.data[latest_entry][key]):
                node.data.setdefault(new_time_key, {})[key] = new_data[key]

                # fresh data per round ['fd'] per round, fresh data describes data that is updated or added in this node
                node.data_flow_per_round[node.cycle].setdefault('fd', 0)
                node.data_flow_per_round[node.cycle]['fd'] += 1
            else:
                node.data.setdefault(new_time_key, {})[key] = node.data[latest_entry][key]
        # inc data doesnt store the data of IP
        elif key in node.data[latest_entry] and key not in new_data:
            node.data.setdefault(new_time_key, {})[key] = node.data[latest_entry][key]
        # node doesnt store the data of IP
        else:
            node.data.setdefault(new_time_key, {})[key] = new_data[key]
            # node.data[key] = new_data[key]
            # new data per round ['nd'] per round (nd is data from an unknown node -> fd = nd)
            node.data_flow_per_round[node.cycle].setdefault('nd', 0)
            node.data_flow_per_round[node.cycle].setdefault('fd', 0)
            node.data_flow_per_round[node.cycle]['nd'] += 1
            node.data_flow_per_round[node.cycle]['fd'] += 1
        # only for deleted nodes
        if key in node.data[latest_entry] and key in new_data:
            merged_failure_list = list(set(list1).union(set(list2)))
            node.data[new_time_key][key]["hbState"]["failureList"] = merged_failure_list
    # TODO update Database
    # send both data and data_flow_per_round to monitor
    # TODO: Save latest data snapshot with key = self.gossip_counter in data
    if new_time_key not in node.data:
        print("No new data to send", flush=True)
        data_to_send_to_monitor = node.data[latest_entry]
    else:
        data_to_send_to_monitor = node.data[new_time_key]
    to_send = {'data': data_to_send_to_monitor, 'data_flow_per_round': node.data_flow_per_round[node.cycle]}
    # TODO: Session here
    if node.is_send_data_back == "1":
        node.session_to_monitoring.post(
            'http://{}:{}/receive_node_data?ip={}&port={}&round={}'.format(node.monitoring_address,node.client_port, node.ip,
                                                                             node.port,
                                                                             inc_round), json=to_send)


@gossip.route('/start_node', methods=['POST'])
def start_node():
    init_data = request.get_json()
    monitoring_address = init_data["monitoring_address"]
    client_port = init_data["client_port"]
    database_address = init_data["database_address"]
    node_list = init_data["node_list"]
    target_count = init_data["target_count"]
    gossip_rate = init_data["gossip_rate"]
    node_ip = init_data["node_ip"]
    is_send_data_back = init_data["is_send_data_back"]
    push_mode = init_data["push_mode"]
    node = Node.instance()
    time.sleep(10)
    client_thread = threading.Thread(target=node.start_gossiping, args=(target_count, gossip_rate))
    counter_thread = threading.Thread(target=node.start_gossip_counter)
    node.set_params(node_ip,
                    request.headers.get('Host').split(':')[1], 0,
                    node_list, {}, True, 0, 0, monitoring_address, database_address,
                    is_send_data_back=is_send_data_back,
                    client_thread=client_thread, counter_thread=counter_thread, data_flow_per_round={},
                    push_mode=push_mode, client_port=client_port)
    client_thread.start()
    counter_thread.start()

    # configure metric priorities and deltas if the orchestrator sent them
    if 'metric_priorities' in init_data:
        METRIC_PRIORITIES.update(init_data['metric_priorities'])
    
    if 'metric_deltas' in init_data:
        METRIC_DELTAS.update(init_data['metric_deltas'])

    return "OK"


@gossip.route('/register_new_node', methods=['POST'])
def register_new_node():
    Node.instance().node_list.append(request.get_json())
    return "OK"


@gossip.route('/get_data_from_node', methods=['GET'])
def get_data_from_node():
    return Node.instance().data


@gossip.route('/get_recent_data_from_node', methods=['GET'])
def get_recent_data_from_node():
    data = Node.instance().data
    latest_entry = max(data.keys(), key=int)
    return data[latest_entry]


@gossip.route('/get_nodelist_from_node', methods=['GET'])
def get_nodelist_from_node():
    return json.dumps(Node.instance().node_list)


@gossip.route('/hello_world', methods=['GET'])
def get_hello_from_node():
    return "Hello from gossip agent!"


# Add new endpoint

@gossip.route('/metrics_priority_stats', methods=['GET'])
def get_metrics_priority_stats():
    """Get statistics about priority-based metric filtering"""
    node = Node.instance()
    
    # Calculate stats if node has data
    if len(node.data) == 0:
        return json.dumps({"error": "No data available"})
    
    # Get sent/filtered counts
    metrics_sent = node.metrics_sent_count if hasattr(node, 'metrics_sent_count') else 0
    metrics_filtered = node.metrics_filtered_count if hasattr(node, 'metrics_filtered_count') else 0
    
    # Get per-round metrics stats
    per_round_stats = {}
    for round_num, stats in node.data_flow_per_round.items():
        per_round_stats[round_num] = {
            'metrics_sent': stats.get('metrics_sent', 0),
            'metrics_filtered': stats.get('metrics_filtered', 0)
        }
    
    # Return statistics
    return json.dumps({
        'total_metrics_sent': metrics_sent,
        'total_metrics_filtered': metrics_filtered,
        'bandwidth_savings_percent': round(100 * metrics_filtered / (metrics_sent + metrics_filtered) if (metrics_sent + metrics_filtered) > 0 else 0, 2),
        'per_round_stats': per_round_stats,
        'priorities': {k: v for k, v in METRIC_PRIORITIES.items()},
        'deltas': {k: v for k, v in METRIC_DELTAS.items()}
    })


if __name__ == "__main__":
    # get port from container
    gossip.run(host='0.0.0.0', debug=True, threaded=True)
```

---

### 3. `src/app/node.py`
This module defines the core architectural `Node` class containing the state and gossip logic for an individual participant in the distributed network. It determines when to send messages based on the Value of Information (VoI) utilizing priority and delta thresholds, processes inbound topology updates, handles the push-pull metadata exchange logic, and tracks peer failure (3-strike rule).

```python
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
    node = Node.instance()
    
    # Calculate Bandwidth (Mbps)
    current_network_bytes = psutil.net_io_counters().bytes_recv + psutil.net_io_counters().bytes_sent
    current_time = time.time()
    
    if node.last_network_bytes == 0:
        # First call, initialize values and return 0
        node.last_network_bytes = current_network_bytes
        node.last_network_time = current_time
        bandwidth_mbps = 0.0
    else:
        delta_bytes = current_network_bytes - node.last_network_bytes
        delta_time = current_time - node.last_network_time
        
        # Avoid division by zero
        if delta_time > 0:
            bandwidth_mbps = (delta_bytes * 8) / (delta_time * 1024 * 1024)
        else:
            bandwidth_mbps = 0.0
            
        node.last_network_bytes = current_network_bytes
        node.last_network_time = current_time
    
    # Calculate Storage (Usage %)
    storage_percent = psutil.disk_usage('/').percent
    
    # Get current node-specific resource usage
    # (Using non-blocking cpu_percent() to avoid hanging the gossip thread)
    cpu_usage = node.node_process.cpu_percent(interval=None)
    memory_usage = node.node_process.memory_percent()
    
    # Get current metric values
    current_metrics = {
        "cpu": cpu_usage,
        "memory": memory_usage,
        "network": bandwidth_mbps,
        "storage": storage_percent
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
    if isinstance(value, (int, float)) and isinstance(prev, (int, float)):
        if metric in ("network", "storage"):
            denom = max(abs(value), abs(prev))
            delta_percent = 0.0 if denom == 0 else (abs(value - prev) / denom) * 100
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
        
        # Sessions — instance scope for experiment isolation
        self.session_to_monitoring = requests.Session()
        self.gossip_session = requests.Session()

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

    def close_sessions(self):
        """Explicitly close connection pools for this node."""
        try:
            if hasattr(self, 'session_to_monitoring'):
                self.session_to_monitoring.close()
            if hasattr(self, 'gossip_session'):
                self.gossip_session.close()
        except Exception as e:
            logger.error(f"[Session] Error closing node sessions: {e}")

    def get_random_nodes(self, node_list, target_count):
        """Return a random sample of peers, excluding self."""
        filtered_nodes = [node for node in node_list if node['ip'] != self.ip]
        if not filtered_nodes:
            return []
        sample_size = min(target_count, len(filtered_nodes))
        return secrets.SystemRandom().sample(filtered_nodes, sample_size)

    def start_gossip_counter(self):
        """OBSOLETE: Gossip counter is now driven by transmit()."""
        pass

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
        # Increment round ID (gossip counter) for every round to ensure freshness
        self.gossip_counter += 1
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

        # Use the already-decided own_recent_data from get_new_data directly
        # to avoid double-filtering that undoes VoI/delta logic.
        metadata = {
            key: node_data['counter']
            for key, node_data in time_data.items()
            if key != own_key and 'counter' in node_data
        }

        return {'metadata': metadata, own_key: own_recent_data}

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
            to_send = self.data.copy()
            to_push = {k: v for k, v in to_send.items() if k != latest_time_key}
            
            try:
                res = self.session_to_monitoring.post(
                    'http://{}:{}/push_data_to_database?ip={}&port={}&round={}'.format(
                        self.monitoring_address, self.client_port,
                        self.ip, self.port, self.cycle
                    ),
                    json=to_push,
                    timeout=5
                )
                if res.status_code < 400:
                    # Successful push, prune local history
                    self.data = {latest_time_key: latest_data}
                else:
                    logger.error(f"[Prune] Push failed with status {res.status_code}. Retaining history.")
            except Exception as e:
                logger.error(f"[Prune] Push exception: {e}. Retaining history.")

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
            if response.status_code >= 400:
                self.update_failure_data(new_time_key, n)
            else:
                self.reset_failure_data(new_time_key, n["ip"] + ':' + n["port"])
        except Exception as e:
            logging.error("Error while sending message to node {}: {}".format(n, e))
            self.update_failure_data(new_time_key, n)

    def update_failure_data(self, new_time_key, n):
        """Record a failed contact attempt against peer n (heartbeat / 3-strike)."""
        peer_key = n["ip"] + ':' + n["port"]
        own_key = self.ip + ':' + self.port
        hb_state = self.data[new_time_key].setdefault(peer_key, {}).setdefault("hbState", {})
        
        # Guard: only add own_key to failureList if not already there
        failure_list = hb_state.setdefault("failureList", [])
        if own_key not in failure_list:
            failure_list.append(own_key)
            
        # Always increment failureCount on every reported failure
        f_count = hb_state.get("failureCount", 0) + 1
        hb_state["failureCount"] = f_count
        
        if f_count >= 3:
            self.delete_node_from_nodelist(peer_key)
            hb_state["nodeAlive"] = False

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

    # Sessions — Moved to __init__ for instance scope

```

---

### 4. `src/app/singleton.py`
A helper class implementing the Singleton pattern. It is used heavily by the `Node` implementation ensuring that all HTTP requests, background threads, and functions share access to a single instance of the node configuration and state throughout the application's runtime.

```python
#TODO: Link Stackoverflow

class Singleton:
    """
    A non-thread-safe helper class to ease implementing singletons.
    This should be used as a decorator -- not a metaclass -- to the
    class that should be a decorator.

    The decorated class can define one `__init__` function that
    takes only the `self` argument. Also, the decorated class cannot be
    inherited from. Other than that, there are no restrictions that apply
    to the decorated class.

    To get the decorator instance, use the `instance` method. Trying
    to use `__call__` will result in a `TypeError` being raised.

    """

    def __init__(self, decorated):
        self._decorated = decorated

    def instance(self):
        """
        Returns the decorator instance. Upon its first call, it creates a
        new instance of the decorated class and calls its `__init__` method.
        On all subsequent calls, the already created instance is returned.
        """
        try:
            return self._instance
        except AttributeError:
            self._instance = self._decorated()
            return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)
```

---

### 5. `src/app/utility.py`
A small utility library containing functions like `mk_digest` which uses SHA256 hashing to generate unique fingerprints for state snapshots. This is critical in the gossip loop to determine system convergence.

```python
import json
import hashlib


# Utility functions for the Node class
def mk_digest(to_digest):
    nested_dict_str = json.dumps(to_digest, sort_keys=True)
    hash_object = hashlib.sha256()
    hash_object.update(nested_dict_str.encode('utf-8'))
    digest = hash_object.hexdigest()
    return digest



```

---

### 6. `src/app/query.py`
Defines the client-side logic to query information safely and consistently out of the distributed network. It executes a quorum-based query where multiple nodes are polled. If their state digests and counters match, it validates consensus and correctly returns ground-truth data.

```python
import random
import time
import requests

# max number of quorum attempts before we give up
MAX_QUERY_RETRIES = 30

def query(node_list, quorum_size, target_node_ip, target_node_port, docker_ip):
    def build_url(node, path):
        host = docker_ip if docker_ip else node["ip"]
        return f"http://{host}:{node['port']}{path}"

    target_key = f"{target_node_ip}:{target_node_port}"

    for attempt in range(MAX_QUERY_RETRIES):
        # 1. Pick a random quorum
        random_nodes = random.sample(node_list, quorum_size)

        metadatas = {}
        total_messages = 0

        # 2. Gather metadata
        for node in random_nodes:
            total_messages += 1
            try:
                resp = requests.get(build_url(node, "/metadata"), timeout=5)
                resp.raise_for_status()
                data = resp.json()[target_key]
                metadatas[f"{node['ip']}:{node['port']}"] = data
            except Exception as e:
                print(f"Node {node['ip']}:{node['port']} not responding: {e}")

        # 3. Check if full quorum replied
        if len(metadatas) == quorum_size:
            # Counter consensus
            counters = [d["counter"] for d in metadatas.values()]
            if len(set(counters)) == 1:
                # Digest consensus
                digests = [d["digest"] for d in metadatas.values()]
                if len(set(digests)) == 1:
                    # 4. Fetch actual data
                    first_node = random_nodes[0]
                    data_resp = requests.get(
                        build_url(first_node, "/get_recent_data_from_node"),
                        timeout=5
                    )
                    data_resp.raise_for_status()
                    result = data_resp.json()[target_key]
                    print(f"Query result: {result}")
                    return total_messages, result

        # small backoff before next attempt
        time.sleep(0.5)

    # if we get here, quorum was never reached
    raise RuntimeError(f"Query failed: could not reach quorum consensus after {MAX_QUERY_RETRIES} attempts")

```

---

### 7. `src/query_client.py`
A routing facade that exports the query functionality defined in `src/app/query.py` to the older `monitoring.py` scripts inside experiments so they can verify network state without directly importing from the deeper nested path.

```python
# re-export query() so monitoring.py can do: from src import query_client
from src.app.query import query  # noqa: F401

```

---

### 8. `experiments/connector_db.py`
This handles the SQLite database operations for the orchestrator. It outlines functions and classes that abstract table creation, inserts of nodes, storage bounds, experiment records, and the detailed metrics sent or filtered out across all network rounds.

```python
import os
import sqlite3
import configparser


parser = configparser.ConfigParser()
parser.read(os.path.join(os.path.dirname(__file__), 'config.ini'))


def get_connection():
    conn = sqlite3.connect(
        os.path.join(os.path.dirname(__file__), parser.get('database', 'db_file')), 
        check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn




def insert_into_round_of_node(run_id, ip, port, this_round, nd, fd, rm, ic, bytes_of_data):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM round_of_node WHERE run_id = ? AND ip = ? AND port = ? AND round = ?",
                       (run_id, ip, port, this_round))
        cursor.execute("INSERT INTO round_of_node ("
                       "run_id,"
                       "ip,"
                       "port,"
                       "round,"
                       "nd,"
                       "fd,"
                       "rm,"
                       "ic,"
                       "bytes_of_data) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (run_id,
                        ip,
                        port,
                        this_round,
                        nd,
                        fd,
                        rm,
                        ic,
                        bytes_of_data))
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        print("Error db: {}".format(e))
        return False


def insert_into_round_of_node_max_round(run_id, ip, port, this_round, nd, fd, rm, ic, bytes_of_data):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM round_of_node_max_round WHERE run_id = ? AND ip = ? AND port = ? AND round = ?",
                       (run_id, ip, port, this_round))
        cursor.execute("INSERT INTO round_of_node_max_round ("
                       "run_id,"
                       "ip,"
                       "port,"
                       "round,"
                       "nd,"
                       "fd,"
                       "rm,"
                       "ic,"
                       "bytes_of_data) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (run_id,
                        ip,
                        port,
                        this_round,
                        nd,
                        fd,
                        rm,
                        ic,
                        bytes_of_data))
        connection.commit()
        connection.close()
        return True
    except Exception as e:
        print("Error db: {}".format(e))
        return False

class NodeDB:
    def _connect(self):
        conn = sqlite3.connect(
            os.path.join(os.path.dirname(__file__), parser.get('database', 'db_file')), 
            check_same_thread=False
        )
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def __init__(self):
        self.connection = self._connect()
        self.cursor = self.connection.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS unique_entries (
                id INTEGER PRIMARY KEY,
                key TEXT,
                value TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_entries (
                id INTEGER PRIMARY KEY,
                node TEXT,
                round INTEGER,
                key TEXT,
                unique_entry_id INTEGER,
                FOREIGN KEY (unique_entry_id) REFERENCES unique_entries(id)
            )
        ''')
        self.connection.commit()
        self.connection.close()

    def get_connection(self):
        return sqlite3.connect('NodeStorage.db', check_same_thread=False)


class PrioMonDB:
    def __init__(self):
        self.connection = get_connection()
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS experiment ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS run ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "experiment_id INTEGER references experiment(id), "
            "run_count INTEGER, "
            "node_count INTEGER, "
            "gossip_rate INTEGER, "
            "target_count INTEGER, "
            "convergence_round TEXT, "
            "convergence_message_count TEXT, "
            "convergence_time TEXT)"
        )
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS round_of_node ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id BIGINT references run(id), "
            "ip TEXT, "
            "port TEXT, "
            "round INTEGER, "
            "nd INTEGER, "
            "fd INTEGER, "
            "rm INTEGER, "
            "ic INTEGER, "
            "bytes_of_data INTEGER)")
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS round_of_node_max_round ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id BIGINT references run(id), "
            "ip TEXT, "
            "port TEXT, "
            "round INTEGER, "
            "nd INTEGER, "
            "fd INTEGER, "
            "rm INTEGER, "
            "ic INTEGER, "
            "bytes_of_data INTEGER)")
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS query ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id BIGINT references run(id), "
            "node_count INTEGER, "
            "query_num INTEGER,"
            "failure_percent INTEGER, "
            "time_to_query TEXT, "
            "total_messages_for_query INTEGER, "
            "success TEXT)"
        )
        # tables for priority-based metric tracking (monitoring.py queues inserts here)
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS round_metrics_stats ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id BIGINT references run(id), "
            "node_ip TEXT, "
            "node_port TEXT, "
            "round INTEGER, "
            "metrics_sent INTEGER, "
            "metrics_filtered INTEGER, "
            "timestamp REAL)")
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS metric_transmissions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id BIGINT references run(id), "
            "node_ip TEXT, "
            "node_port TEXT, "
            "round INTEGER, "
            "metric_type TEXT, "
            "was_sent INTEGER, "
            "metric_value REAL, "
            "timestamp REAL)")
        self.connection.commit()
        self.connection.close()

    def insert_into_experiment(self, timestamp):
        try:
            self.connection = get_connection()
            self.cursor = self.connection.cursor()
            self.cursor.execute("INSERT INTO experiment (timestamp) VALUES (?)", (timestamp,))
            to_return = self.cursor.lastrowid
            self.connection.commit()
            self.connection.close()
            return to_return
        except Exception as e:
            print("Error DB Insert: {}".format(e))
            return -1

    def insert_into_run(self, experiment_id, run_count, node_count, gossip_rate, target_count):
        try:
            self.connection = get_connection()
            self.cursor = self.connection.cursor()
            self.cursor.execute("INSERT INTO run ("
                                "experiment_id,"
                                "run_count, "
                                "node_count, "
                                "gossip_rate, "
                                "target_count) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (experiment_id,
                                 run_count,
                                 node_count,
                                 gossip_rate,
                                 target_count
                                 ))
            to_return = self.cursor.lastrowid
            self.connection.commit()
            self.connection.close()
            return to_return
        except Exception as e:
            print("Error DB Insert run: {}".format(e))
            return -1

    def save_query_in_database(self, run_id, node_count, i, failure_percent, time_to_query, total_messages_for_query,
                               success):
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO query ("
                "run_id,"
                "node_count, "
                "query_num,"
                "failure_percent, "
                "time_to_query, "
                "total_messages_for_query, "
                "success)"
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id,
                 node_count,
                 i,
                 failure_percent,
                 time_to_query,
                 total_messages_for_query,
                 success
                 ))
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print("Exception in save_query_in_database: {}".format(e))

    def insert_into_converged_run(self, run_id, convergence_round, convergence_message_count, convergence_time):
        try:
            self.connection = get_connection()
            self.cursor = self.connection.cursor()
            self.cursor.execute("UPDATE run SET "
                                "convergence_round = ?, "
                                "convergence_message_count = ?, "
                                "convergence_time = ? "
                                "WHERE id = ?",
                                (convergence_round,
                                 convergence_message_count,
                                 convergence_time,
                                 run_id
                                 ))
            to_return = self.cursor.lastrowid
            self.connection.commit()
            self.connection.close()
            return to_return
        except Exception as e:
            print("Error DB Update run: {}".format(e))
            return -1
```

---

### 9. `experiments/schema.py`
A very simple diagnostic script that when executed iterates over the `sqlite_master` table and dumps all the creation schemas. Often helpful for quick checks into what tables currently exist in `PrioMonDB.db`.

```python
import sqlite3

conn = sqlite3.connect("PrioMonDB.db")
cursor = conn.cursor()

# Get all schema creation statements
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
schemas = cursor.fetchall()

print("=== Database Schema ===")
for schema in schemas:
    print(schema[0])
    print()

conn.close()
```

---

### 10. `experiments/plot.py`
A final analytics script. After an experiment concludes, this file reads the persistent metrics saved by the orchestrator and utilizes matplotlib to chart out the VoI bandwidth efficiencies and query success behaviors against failure injection rates.

```python
import sqlite3
import matplotlib.pyplot as plt
import os

# the actual database for this project
dbname = 'PrioMonDB.db'

class PrioMonDataDB:
    def __init__(self):
        # We assume the script is run from the experiments/ directory 
        # or root directory. If the db isn't found, try experiments/.
        db_path = dbname
        if not os.path.exists(db_path):
            db_path = os.path.join(os.path.dirname(__file__), dbname)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.connection.cursor()

    def get_query_success_by_failure_rate(self):
        try:
            self.cursor.execute(
                "SELECT failure_percent, "
                "AVG(CASE WHEN success = 'True' OR success = '1' THEN 1 ELSE 0 END) "
                "FROM query GROUP BY failure_percent"
            )
            return self.cursor.fetchall()
        except Exception as e:
            print("Error DB Query (get_query_success_by_failure_rate): {}".format(e))
            return []

    def get_bandwidth_savings_over_time(self):
        try:
            self.cursor.execute(
                "SELECT round, SUM(metrics_sent), SUM(metrics_filtered) "
                "FROM round_metrics_stats "
                "GROUP BY round "
                "ORDER BY round"
            )
            return self.cursor.fetchall()
        except Exception as e:
            print("Error DB Query (get_bandwidth_savings_over_time): {}".format(e))
            return []

    def get_total_bandwidth_saved(self):
        try:
            self.cursor.execute(
                "SELECT SUM(metrics_sent), SUM(metrics_filtered) "
                "FROM round_metrics_stats"
            )
            return self.cursor.fetchone()
        except Exception as e:
            print("Error DB Query (get_total_bandwidth_saved): {}".format(e))
            return (0, 0)

    def get_transmissions_by_metric_type(self):
        try:
            self.cursor.execute(
                "SELECT metric_type, "
                "SUM(CASE WHEN was_sent = 1 THEN 1 ELSE 0 END) as sent, "
                "SUM(CASE WHEN was_sent = 0 THEN 1 ELSE 0 END) as filtered "
                "FROM metric_transmissions "
                "GROUP BY metric_type"
            )
            return self.cursor.fetchall()
        except Exception as e:
            print("Error DB Query (get_transmissions_by_metric_type): {}".format(e))
            return []


def plot_query_success_vs_failure_rate(db):
    data = db.get_query_success_by_failure_rate()
    if not data:
        print("No data for Query Success vs Failure Rate.")
        return
    failure_rates = [row[0] for row in data]
    success_rates = [row[1] for row in data]
    
    plt.figure(figsize=(10, 6))
    plt.plot(failure_rates, success_rates, marker='o', color='b')
    plt.xlabel('Failure Rate (%)')
    plt.ylabel('Query Success Rate')
    plt.title('Query Success vs Node Failure Rate')
    plt.grid(True)
    plt.savefig('query_success_vs_failure_rate.png')
    print("Saved query_success_vs_failure_rate.png")


def plot_bandwidth_savings_over_time(db):
    data = db.get_bandwidth_savings_over_time()
    if not data:
        print("No data for Bandwidth Savings Over Time.")
        return
        
    rounds = [row[0] for row in data]
    sent = [row[1] for row in data]
    filtered = [row[2] for row in data]
    
    plt.figure(figsize=(10, 6))
    plt.plot(rounds, sent, label='Metrics Sent (Bandwidth Used)', color='red', marker='o')
    plt.plot(rounds, filtered, label='Metrics Filtered (Bandwidth Saved)', color='green', marker='x')
    plt.xlabel('Gossip Round')
    plt.ylabel('Number of Metrics')
    plt.title('Metrics Transmission Over Time (Bandwidth Savings)')
    plt.legend()
    plt.grid(True)
    plt.savefig('bandwidth_savings_over_time.png')
    print("Saved bandwidth_savings_over_time.png")


def plot_total_bandwidth_saved(db):
    data = db.get_total_bandwidth_saved()
    if not data or data == (None, None) or (data[0] == 0 and data[1] == 0):
        print("No data for Total Bandwidth Saved Pie Chart.")
        return
        
    sent, filtered = data
    labels = ['Metrics Sent', 'Metrics Filtered (Saved)']
    sizes = [sent, filtered]
    colors = ['#ff9999','#66b3ff']
    
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.title('Total Metric Bandwidth Usage')
    plt.axis('equal')
    plt.savefig('total_bandwidth_saved.png')
    print("Saved total_bandwidth_saved.png")


def plot_transmissions_by_metric_type(db):
    data = db.get_transmissions_by_metric_type()
    if not data:
        print("No data for Transmissions By Metric Type.")
        return
        
    metrics = [row[0] for row in data]
    sent = [row[1] for row in data]
    filtered = [row[2] for row in data]
    
    x = range(len(metrics))
    width = 0.35
    
    plt.figure(figsize=(10, 6))
    plt.bar(x, sent, width, label='Sent', color='salmon')
    plt.bar([i + width for i in x], filtered, width, label='Filtered (Saved)', color='lightgreen')
    
    plt.xlabel('Metric Type')
    plt.ylabel('Count')
    plt.title('Transmission vs Filtering by Metric Type')
    plt.xticks([i + width/2 for i in x], metrics)
    plt.legend()
    plt.grid(axis='y')
    plt.savefig('transmissions_by_metric_type.png')
    print("Saved transmissions_by_metric_type.png")


if __name__ == '__main__':
    db = PrioMonDataDB()
    
    # Generate all plots
    plot_query_success_vs_failure_rate(db)
    plot_bandwidth_savings_over_time(db)
    plot_total_bandwidth_saved(db)
    plot_transmissions_by_metric_type(db)
    
    # We do a final plt.show() if running interactively, otherwise just save images.
    # plt.show()
    print("All plotting routines finished.")

```

---

