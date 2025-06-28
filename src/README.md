# EdgeWatch Core Modules

This directory contains the core components of the EdgeWatch distributed monitoring system.

## Architecture Overview

EdgeWatch implements a decentralized monitoring architecture using gossip-based communication protocols. The core modules provide the fundamental building blocks for edge node management, configuration, and inter-node communication.

## Core Components

### EdgeNode (`edge_node.py`)
The main monitoring node implementation that handles:
- **System Metrics Collection**: CPU, memory, network, and storage monitoring
- **Gossip Communication**: Peer-to-peer information dissemination
- **Adaptive Filtering**: Priority-based metric transmission optimization
- **Failure Detection**: Node health monitoring and fault tolerance
- **Data Management**: Local data storage and synchronization

Key Features:
- Singleton pattern for node management
- Configurable metric collection priorities
- Dynamic threshold-based data filtering
- Automatic failure recovery mechanisms

### ConfigManager (`config_manager.py`)
Thread-safe configuration management system that provides:
- **Centralized Configuration**: Single source of truth for all settings
- **Dynamic Loading**: Runtime configuration updates
- **Type Safety**: Automatic type conversion and validation
- **Caching**: Performance optimization through intelligent caching
- **File Management**: Automatic file I/O and persistence

Configuration Sections:
- `EdgeWatch`: Core application settings
- `Network`: Communication and connectivity parameters
- `Monitoring`: Data collection and processing options
- `Storage`: Database and persistence configuration
- `Logging`: Application logging and debugging settings

## Communication Protocol

EdgeWatch uses a sophisticated gossip-based protocol for distributed communication:

1. **Metadata Exchange**: Lightweight metadata sharing to determine data freshness
2. **Selective Synchronization**: Only transfer new or updated information
3. **Priority-based Filtering**: Reduce network overhead through intelligent filtering
4. **Failure Detection**: Heartbeat mechanism with configurable thresholds
5. **Adaptive Scheduling**: Dynamic adjustment of communication frequencies

## Data Flow

```
[System Metrics] → [Priority Filter] → [Gossip Protocol] → [Remote Nodes]
       ↓                    ↓                   ↓              ↓
[Local Storage] ← [Data Aggregation] ← [Metadata Exchange] ← [Failure Detection]
```

## Getting Started

### Basic Usage

```python
from edgewatch.core.edge_node import EdgeNode
from edgewatch.core.config_manager import ConfigManager

# Initialize configuration
config = ConfigManager.instance()
config.load_config_file('config/default.ini')

# Create and configure edge node
node = EdgeNode.instance()
node.set_params(
    ip="192.168.1.100",
    port=8080,
    cycle=0,
    node_list={"192.168.1.101": {"ip": "192.168.1.101", "port": 8080}},
    data={},
    is_alive=True,
    gossip_counter=0,
    failure_counter=0,
    monitoring_address="192.168.1.200",
    database_address="192.168.1.201",
    is_send_data_back=True,
    client_thread=None,
    counter_thread=None,
    data_flow_per_round={},
    push_mode="1",
    client_port=5000
)

# Start monitoring
node.start_gossiping(target_count=3, gossip_rate=2.0)
```

### Configuration Example

```python
# Load custom configuration
config = ConfigManager.instance()
config.load_config_file('config/production.ini')

# Access configuration values
heartbeat_interval = config.get_int('Network', 'heartbeat_interval')
log_level = config.get('Logging', 'log_level')
enable_metrics = config.get_boolean('Monitoring', 'enable_metrics')

# Update configuration at runtime
config.set('Network', 'default_port', '9090')
config.save_config()
```

## Performance Considerations

- **Metric Filtering**: Reduces network traffic by up to 70% through intelligent priority-based filtering
- **Singleton Pattern**: Minimizes memory overhead and ensures consistent state
- **Configurable Thresholds**: Allows fine-tuning of performance vs. accuracy trade-offs
- **Asynchronous Communication**: Non-blocking network operations for improved responsiveness

## Error Handling

The core modules implement comprehensive error handling:
- Configuration validation and fallback mechanisms
- Network timeout and retry logic
- Graceful degradation during node failures
- Automatic recovery and state synchronization

## Thread Safety

All core components are designed to be thread-safe:
- ConfigManager uses locks for safe concurrent access
- EdgeNode handles multiple communication threads
- Shared data structures are protected with appropriate synchronization

## Extension Points

The core architecture supports extensions through:
- Custom metric collectors
- Pluggable communication protocols
- Configurable storage backends
- Custom failure detection algorithms
