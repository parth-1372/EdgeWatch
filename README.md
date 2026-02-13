# EdgeWatch - VoI Emulsion Experiment

**Edge computing monitoring with Value of Information (VoI) based filtering**

This repository implements the **Emulsion experiment** - integrating VoI-based metric filtering from the DEmon project into EdgeWatch's monitoring infrastructure for bandwidth-efficient edge monitoring.

## 🎯 What is This?

EdgeWatch is a research project exploring intelligent metric filtering for edge computing environments. The core innovation is the **VoI (Value of Information)** filtering approach that decides which metrics to send based on:

1. **Priority Levels** - Critical metrics update every round, less critical ones update periodically
2. **Delta Thresholds** - Only send when significant change is detected
3. **Adaptive Scheduling** - Smart timing based on metric importance

### Expected Results
- **Bandwidth Reduction**: 45-60% less data transmitted
- **Accuracy**: >95% of important changes still detected  
- **Minimal Overhead**: <100ms processing time

## 📁 Project Structure

```
EdgeWatch/
├── src/
│   ├── experiments/emulsion/    # ⭐ VoI experiment implementation
│   │   ├── voi_metrics.py       # Core filtering logic
│   │   ├── config.py            # Priority & delta configurations
│   │   ├── emulsion_node.py     # Node with VoI integration
│   │   ├── experiment_runner.py # Experiment orchestration
│   │   └── README.md            # Detailed experiment docs
│   │
│   ├── monitoring/              # Base monitoring components
│   ├── core/                    # Core utilities
│   └── main.py                  # Main entry point
│
├── deployment/                  # Docker deployment files
└── config/                      # Configuration files
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- psutil library: `pip install psutil`

### Running the Emulsion Experiment

#### Basic Experiment
```bash
# Run with VoI filtering enabled
python -m src.experiments.emulsion.experiment_runner \
  --nodes 10 \
  --rounds 100 \
  --voi-enabled

# Run without VoI (baseline)
python -m src.experiments.emulsion.experiment_runner \
  --nodes 10 \
  --rounds 100
```

#### Comparison Mode
```bash
# Run both VoI and baseline for comparison
python -m src.experiments.emulsion.experiment_runner \
  --compare \
  --nodes 20 \
  --rounds 200
```

### Configuration

Edit `src/experiments/emulsion/config.py` to customize:

```python
# Metric priorities
METRIC_PRIORITIES = {
    "cpu_percent": MetricPriority.HIGH,      # Every round
    "memory_percent": MetricPriority.MEDIUM, # Every 5 rounds
    "disk_usage": MetricPriority.LOW,        # Every 10 rounds
}

# Delta thresholds (% change to trigger update)
METRIC_DELTAS = {
    "cpu_percent": 5.0,    # Send if >5% change
    "memory_percent": 7.0,
    "disk_usage": 10.0,
}
```

## 📊 Understanding VoI Filtering

### How It Works

```python
from src.experiments.emulsion import VoIMetricFilter

# Create filter
filter = VoIMetricFilter()

# Check if metric should be sent
should_send, reason = filter.should_send_metric("cpu_percent", 45.2)

if should_send:
    # Send metric
    print(f"Sending: {reason}")
else:
    # Skip metric
    print(f"Skipped: {reason}")
```

### Decision Logic

1. **First Time**: Always send new metrics
2. **High Priority**: Always send (e.g., CPU, error rate)
3. **Scheduled**: Send based on priority interval
   - Medium priority: Every 5 rounds
   - Low priority: Every 10 rounds
4. **Delta Triggered**: Send when change exceeds threshold
   - CPU change >5%
   - Memory change >7%
   - Disk change >10%

## 📈 Experiment Results

Results are saved as JSON files with detailed statistics:

```json
{
  "experiment_config": {
    "num_nodes": 10,
    "voi_enabled": true
  },
  "experiment_stats": {
    "total_metrics_collected": 5000,
    "total_metrics_sent": 2200,
    "total_metrics_filtered": 2800,
    "average_bandwidth_saved": 56.0
  }
}
```

## 🔬 Use in Research

### Integration Example

```python
from src.experiments.emulsion import EmulsionNode

# Create node with VoI filtering
node = EmulsionNode("edge-node-1", enable_voi=True)

# Collect and filter metrics automatically
gossip_message = node.prepare_gossip_message()

# Get statistics
stats = node.get_node_statistics()
print(f"Bandwidth saved: {stats['bandwidth_saved']:.1f}%")
```

### Custom Priorities

```python
from src.experiments.emulsion import VoIMetricFilter, MetricPriority

# Custom configuration
custom_priorities = {
    "custom_metric": MetricPriority.HIGH
}

custom_deltas = {
    "custom_metric": 3.0  # 3% change threshold
}

filter = VoIMetricFilter(
    priorities=custom_priorities,
    deltas=custom_deltas
)
```

## 📚 Documentation

- **Detailed Experiment Guide**: [src/experiments/emulsion/README.md](src/experiments/emulsion/README.md)
- **Integration Summary**: [EMULSION_INTEGRATION_SUMMARY.md](EMULSION_INTEGRATION_SUMMARY.md)

## 🔧 Installation

```bash
# Clone repository
git clone https://github.com/parth-1372/EdgeWatch.git
cd EdgeWatch

# Install dependencies
pip install -r requirements.txt

# Run experiments
cd src/experiments/emulsion
python experiment_runner.py --help
```

## 📖 Background

This experiment is part of research on bandwidth-efficient monitoring for edge computing. It builds on the VoI concept from the DEmon (Decentralized Monitoring) project and adapts it for edge infrastructure.

### Key Papers
- DEmon: Context-Aware Gossip-based Decentralised Monitoring
- Value of Information in distributed monitoring systems

## 🛠️ Development

```bash
# Project structure
src/
├── experiments/emulsion/  # Main experiment code
├── monitoring/           # Monitoring infrastructure  
├── core/                 # Utilities
└── main.py              # Entry point
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- **DEmon Project**: Original VoI concept and implementation
- **EdgeWatch**: Base monitoring infrastructure
- Research community for edge computing innovations

---

**Status**: Active research project  
**Focus**: Bandwidth-efficient edge monitoring with VoI filtering

For questions or collaboration: Open an issue on GitHub