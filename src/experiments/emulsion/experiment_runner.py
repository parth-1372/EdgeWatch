"""
Experiment Runner for VoI-based Emulsion
Runs experiments comparing VoI-enabled vs baseline monitoring
"""

import argparse
import logging
import time
import sys
from typing import List, Dict, Any
import json
from datetime import datetime

from .emulsion_node import EmulsionNode
from .config import VoIConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("emulsion.runner")


class ExperimentRunner:
    """Orchestrates VoI emulsion experiments"""
    
    def __init__(self, 
                 num_nodes: int = 10,
                 max_rounds: int = 100,
                 enable_voi: bool = True,
                 gossip_rate: float = 2.0):
        """
        Initialize experiment runner
        
        Args:
            num_nodes: Number of nodes to simulate
            max_rounds: Maximum rounds to run
            enable_voi: Enable VoI filtering
            gossip_rate: Seconds between gossip rounds
        """
        self.num_nodes = num_nodes
        self.max_rounds = max_rounds
        self.enable_voi = enable_voi
        self.gossip_rate = gossip_rate
        
        # Create nodes
        self.nodes: List[EmulsionNode] = []
        for i in range(num_nodes):
            node = EmulsionNode(
                node_id=f"node-{i:03d}",
                enable_voi=enable_voi
            )
            self.nodes.append(node)
        
        # Experiment stats
        self.experiment_stats = {
            "start_time": None,
            "end_time": None,
            "total_rounds": 0,
            "total_metrics_collected": 0,
            "total_metrics_sent": 0,
            "average_bandwidth_saved": 0.0,
        }
        
        logger.info(
            f"Initialized experiment: {num_nodes} nodes, "
            f"{max_rounds} rounds, VoI={'ON' if enable_voi else 'OFF'}"
        )
    
    def run_single_round(self, round_num: int):
        """Execute a single gossip round"""
        logger.debug(f"=== Round {round_num} ===")
        
        # Each node prepares a gossip message
        messages = []
        for node in self.nodes:
            msg = node.prepare_gossip_message()
            messages.append(msg)
        
        # Simulate gossip - each node receives messages from random peers
        # (simplified - in real gossip, nodes send to specific targets)
        for node in self.nodes:
            # Receive a few random messages
            import random
            num_to_receive = min(3, len(messages) - 1)
            sample_msgs = random.sample(
                [m for m in messages if m["node_id"] != node.node_id],
                num_to_receive
            )
            for msg in sample_msgs:
                node.receive_gossip_message(msg)
        
        # Advance all nodes to next cycle
        for node in self.nodes:
            node.advance_cycle()
        
        # Log round stats
        if round_num % 10 == 0:
            self._log_round_stats(round_num)
    
    def _log_round_stats(self, round_num: int):
        """Log statistics for current round"""
        total_sent = sum(n.stats["metrics_sent"] for n in self.nodes)
        total_filtered = sum(n.stats["metrics_filtered"] for n in self.nodes)
        total = total_sent + total_filtered
        
        if total > 0:
            saved_pct = (total_filtered / total) * 100
        else:
            saved_pct = 0
        
        logger.info(
            f"Round {round_num}: "
            f"Sent={total_sent}, Filtered={total_filtered}, "
            f"Bandwidth saved={saved_pct:.1f}%"
        )
    
    def run_experiment(self):
        """Run the complete experiment"""
        logger.info("Starting experiment...")
        self.experiment_stats["start_time"] = datetime.now().isoformat()
        
        try:
            for round_num in range(1, self.max_rounds + 1):
                self.run_single_round(round_num)
                time.sleep(self.gossip_rate)
                
                # Cleanup old data periodically
                if round_num % 20 == 0:
                    for node in self.nodes:
                        node.cleanup_old_data(keep_last_n=10)
            
            self.experiment_stats["end_time"] = datetime.now().isoformat()
            self.experiment_stats["total_rounds"] = self.max_rounds
            
            logger.info("Experiment completed!")
            
        except KeyboardInterrupt:
            logger.warning("Experiment interrupted by user")
            self.experiment_stats["end_time"] = datetime.now().isoformat()
            self.experiment_stats["total_rounds"] = round_num - 1
    
    def collect_results(self) -> Dict[str, Any]:
        """Collect results from all nodes"""
        logger.info("Collecting results...")
        
        # Aggregate statistics
        total_metrics_collected = sum(n.stats["metrics_collected"] for n in self.nodes)
        total_metrics_sent = sum(n.stats["metrics_sent"] for n in self.nodes)
        total_metrics_filtered = sum(n.stats["metrics_filtered"] for n in self.nodes)
        
        if total_metrics_collected > 0:
            bandwidth_saved = (total_metrics_filtered / total_metrics_collected) * 100
        else:
            bandwidth_saved = 0
        
        self.experiment_stats.update({
            "total_metrics_collected": total_metrics_collected,
            "total_metrics_sent": total_metrics_sent,
            "total_metrics_filtered": total_metrics_filtered,
            "average_bandwidth_saved": bandwidth_saved,
        })
        
        # Collect per-node data
        node_results = []
        for node in self.nodes:
            node_results.append({
                "node_id": node.node_id,
                "statistics": node.get_node_statistics(),
            })
        
        results = {
            "experiment_config": {
                "num_nodes": self.num_nodes,
                "max_rounds": self.max_rounds,
                "voi_enabled": self.enable_voi,
                "gossip_rate": self.gossip_rate,
            },
            "experiment_stats": self.experiment_stats,
            "node_results": node_results,
            "voi_config": VoIConfig.get_config_dict(),
        }
        
        return results
    
    def save_results(self, filepath: str):
        """Save experiment results to file"""
        results = self.collect_results()
        
        try:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def print_summary(self):
        """Print experiment summary"""
        results = self.collect_results()
        
        print("\n" + "="*60)
        print("EXPERIMENT SUMMARY")
        print("="*60)
        print(f"Nodes: {self.num_nodes}")
        print(f"Rounds: {self.experiment_stats['total_rounds']}")
        print(f"VoI Filtering: {'ENABLED' if self.enable_voi else 'DISABLED'}")
        print("-"*60)
        print(f"Total Metrics Collected: {self.experiment_stats['total_metrics_collected']}")
        print(f"Total Metrics Sent: {self.experiment_stats['total_metrics_sent']}")
        print(f"Total Metrics Filtered: {self.experiment_stats['total_metrics_filtered']}")
        print(f"Bandwidth Saved: {self.experiment_stats['average_bandwidth_saved']:.2f}%")
        print("="*60 + "\n")


def run_comparison_experiment(num_nodes: int, max_rounds: int, gossip_rate: float):
    """Run both VoI and baseline experiments for comparison"""
    print("\n*** Running BASELINE experiment (no VoI) ***\n")
    baseline_runner = ExperimentRunner(
        num_nodes=num_nodes,
        max_rounds=max_rounds,
        enable_voi=False,
        gossip_rate=gossip_rate
    )
    baseline_runner.run_experiment()
    baseline_results = baseline_runner.collect_results()
    
    print("\n*** Running VoI-ENABLED experiment ***\n")
    voi_runner = ExperimentRunner(
        num_nodes=num_nodes,
        max_rounds=max_rounds,
        enable_voi=True,
        gossip_rate=gossip_rate
    )
    voi_runner.run_experiment()
    voi_results = voi_runner.collect_results()
    
    # Print comparison
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    print(f"{'Metric':<30} {'Baseline':<15} {'VoI-Enabled':<15}")
    print("-"*60)
    
    baseline_sent = baseline_results['experiment_stats']['total_metrics_sent']
    voi_sent = voi_results['experiment_stats']['total_metrics_sent']
    reduction = ((baseline_sent - voi_sent) / baseline_sent * 100) if baseline_sent > 0 else 0
    
    print(f"{'Metrics Sent':<30} {baseline_sent:<15} {voi_sent:<15}")
    print(f"{'Bandwidth Reduction':<30} {'-':<15} {reduction:.1f}%")
    print("="*60 + "\n")
    
    # Save comparison results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    comparison_file = f"emulsion_comparison_{timestamp}.json"
    
    comparison_data = {
        "timestamp": timestamp,
        "baseline": baseline_results,
        "voi_enabled": voi_results,
        "comparison": {
            "metrics_sent_reduction_percent": reduction,
        }
    }
    
    with open(comparison_file, 'w') as f:
        json.dump(comparison_data, f, indent=2, default=str)
    
    print(f"Comparison results saved to: {comparison_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run VoI-based Emulsion experiments"
    )
    parser.add_argument(
        '--nodes', type=int, default=10,
        help='Number of nodes to simulate (default: 10)'
    )
    parser.add_argument(
        '--rounds', type=int, default=100,
        help='Number of rounds to run (default: 100)'
    )
    parser.add_argument(
        '--gossip-rate', type=float, default=2.0,
        help='Seconds between gossip rounds (default: 2.0)'
    )
    parser.add_argument(
        '--voi-enabled', action='store_true', default=False,
        help='Enable VoI filtering (default: False)'
    )
    parser.add_argument(
        '--compare', action='store_true',
        help='Run both baseline and VoI experiments for comparison'
    )
    parser.add_argument(
        '--output', type=str, default=None,
        help='Output file for results (default: auto-generate)'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.compare:
        run_comparison_experiment(args.nodes, args.rounds, args.gossip_rate)
    else:
        runner = ExperimentRunner(
            num_nodes=args.nodes,
            max_rounds=args.rounds,
            enable_voi=args.voi_enabled,
            gossip_rate=args.gossip_rate
        )
        
        runner.run_experiment()
        runner.print_summary()
        
        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            voi_suffix = "voi" if args.voi_enabled else "baseline"
            output_file = f"emulsion_{voi_suffix}_{timestamp}.json"
        
        runner.save_results(output_file)


if __name__ == "__main__":
    main()
