# Demon Monitoring System Emulation

This is an emulation of the Demon Monitoring System, comprising three primary components: `monitoring_exp`, `demon`, and `config`. The system enables you to manage Docker containers running Demon instances and configure experiment hyperparameters.

## Components

### 1. [`monitoring_exp.py`](./monitoring_exp.py)

The `monitoring_exp` component is responsible for creating and scaling Docker containers running Demon. It provides a Flask server with essential endpoints for controlling experiments.

### 2. [`demon`](../../src/demon)

The `demon` component is the core of the system, running within each Docker container. It performs monitoring and management tasks, making it the heart of the Demon Monitoring System.

### 3. [`config.ini`](../config.ini)

The `config` component allows you to configure experiment hyperparameters. Customize the behavior of the Demon Monitoring System by editing the `config.ini` file.

## How to Run

Follow these steps to run the Demon Monitoring System emulation:

### 1. Build the Docker Image

In the [`demon`](../../src/demon) directory, build the Docker image using the provided [`Dockerfile`](../../src/demon/Dockerfile):
    
   ```bash
docker build -f ../../src/demon/Dockerfile -t demonv1 .
```

### 2. Configure Parameters

Edit the [`config.ini`](../config.ini). Ensure the `docker_ip` parameter is correctly set for communication with the Docker client. Besides that following parameters can be configured:
- `node_range` - the range of Demon nodes to be created (ascending order). Note that the the number of nodes is equal to the number of DEmon containers created.
- `target_count_range` - the range of target counts (= gossip count: describes the number of nodes updated from one node in one gossip round) to be used in experiments
- `gossip_rate_range` - the range of gossip rates (interval between each gossip round) to be used in experiments
- `runs` - the number of runs to be performed for each setting (total number of different executions = runs * len(target_count_range) * len(gossip_rate_range) * len(node_range))
- `continue_after_convergence` if set to 1 the run will continue after convergence is reached (all nodes have the same state)
- `push_mode` if set to 1 the data of each node will be pushed to the database every 10th run. This mode can affect the networking performance of your system.
- `query_logic` if set to 1 the query logic will be used (see paper for details). It uses the [`query_client`](../../src/query_client.py) to query the Demon nodes for their state. This mode only works, when `continue_after_convergence` is not set to 1.
- `failure_rate` the rate at which nodes fail (0.0 - 1.0). This param is only used for experiments with `query_logic`.
- `docker_ip` the ip address of the docker client.
- `is_send_data_back` if set to 1 benchmark data of each node will be sent to the monitoring_exp component. This data is used for benchmarking, but can highly infect the networking performance of your system.


### 3. Prepare and start `monitoring_exp.py`
#### Requirements
The non-standard library packages and modules are listed in [`requirements.txt`](./requirements.txt). Install them using the following command:
```bash
pip install -r requirements.txt
```
#### Start

```bash
   python monitoring_exp.py
```

Run the `monitoring_exp.py` script. It launches a Flask Server with your hosts ip-address with key endpoints:

- To initiate experiments based on the configured settings, visit: `http://_ip_:4000/start`
- To delete all Docker containers with the specified Docker image at any time, visit: `http://_ip_:4000/delete_nodes`

Make sure that this Flask Sever is reachable from your Docker Containers.

### 4. Create Demon Nodes

Once `monitoring_exp.py` is running, it will create the specified range of Demon nodes and start Demon instances in each of them. If not specified each run will end when converged till all combinations of the configured parameters are tested. When done, all docker container will be deleted. 


### 5. It's not my job to run/debug this script

If you have no intention to run this script or deal with possible issues you can view the results of our experiments via our [`plots`](./plots).

### 6. It's still not my job to run/debug this script, but I did it anyway

If you tried to run this script and encountered issues, please let us know. We will try to help you as soon as possible.
If you found a bug please do so as well. :-) 

