# VoI-based Emulsion Experiments

This module implements **Value of Information (VoI)** based metric filtering for EdgeWatch, borrowed from the DEmon project's innovative approach to bandwidth-efficient monitoring.

## What is VoI?

Value of Information is an intelligent filtering approach that decides which metrics to send based on:

1. **Priority Levels** - Critical metrics (CPU, error rate) update every round, while slowly-changing metrics (disk usage) update less frequently
2. **Delta Thresholds** - Only send metrics when they change significantly (e.g., CPU change > 5%)
3. **Time-based Scheduling** - Low-priority metrics are sent periodically even without significant changes

## Why "Emulsion"?

Like an emulsion where two normally immiscible liquids mix, this experiment blends DEmon's VoI concept with EdgeWatch's monitoring infrastructure. The goal is to reduce bandwidth usage by 40-60% while maintaining monitoring accuracy.

## Architecture

```
emulsion/
├── voi_metrics.py       # Core VoI filtering logic
├── config.py            # Priority and delta configurations
├── emulsion_node.py     # Node implementation with VoI
└── experiment_runner.py # Experiment orchestration
```

## Key Components

### VoIMetricFilter

The heart of the system - decides what metrics to send:

```python
from experiments.emulsion import VoIMetricFilter, MetricPriority

filter = VoIMetricFilter()
should_send, reason = filter.should_send_metric("cpu_percent", 45.2)
```

### EmulsionNode

Integrates VoI with metric collection:

```python
from experiments.emulsion import EmulsionNode

node = EmulsionNode("node-1", enable_voi=True)
message = node.prepare_gossip_message()  # Auto-filtered metrics
```

## Configuration

Edit `config.py` to customize:

```python
METRIC_PRIORITIES = {
    "cpu_percent": MetricPriority.HIGH,      # Every round
    "memory_percent": MetricPriority.MEDIUM, # Every 5 rounds
    "disk_usage": MetricPriority.LOW,        # Every 10 rounds
}

METRIC_DELTAS = {
    "cpu_percent": 5.0,    # Send if >5% change
    "error_rate": 0.5,     # Very sensitive
    "disk_usage": 10.0,    # Less sensitive
}
```

## Running Experiments

```bash
# Basic experiment
python -m experiments.emulsion.experiment_runner --nodes 10 --rounds 100

# With custom config
python -m experiments.emulsion.experiment_runner --nodes 20 --rounds 200 --voi-enabled

# Comparison mode (VoI vs baseline)
python -m experiments.emulsion.experiment_runner --compare
```

## Expected Results

Based on DEmon experiments:
- **Bandwidth Reduction**: 45-60% less data transmitted
- **Accuracy**: >95% of important changes still detected
- **Latency**: Minimal impact (<100ms overhead)

## Integration with EdgeWatch

VoI filtering can be integrated into EdgeWatch's core monitoring:

```python
# In monitoring/metrics_collector.py
from experiments.emulsion import VoIMetricFilter

class MetricsCollector:
    def __init__(self):
        self.voi_filter = VoIMetricFilter()
    
    def collect_and_filter(self):
        metrics = self.collect()
        filtered, metadata = self.voi_filter.filter_metrics(metrics)
        return filtered
```

## Future Work

- [ ] Adaptive priority adjustment based on system state
- [ ] Machine learning for optimal delta threshold tuning
- [ ] Integration with EdgeWatch's alert system
- [ ] Multi-metric correlation for smarter filtering
- [ ] Real-world deployment validation

## References

- DEmon: Context-Aware Gossip-based Decentralized Monitoring
- Original VoI implementation: `../../../DEmon/src/demon/node.py`

---

**Note**: This is experimental code for research purposes. Test thoroughly before production use!
