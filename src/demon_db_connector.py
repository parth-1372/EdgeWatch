"""
DEmon Database Connector
Connects to DEmon experiment SQLite databases and retrieves results for dashboard visualization
"""

import sqlite3
import pandas as pd
from typing import Dict, List, Any, Optional
import os


class DemonDBConnector:
    """Connects to DEmon experiment databases and retrieves results"""
    
    def __init__(self, db_path: str):
        """
        Initialize database connector
        
        Args:
            db_path: Absolute path to demonDB.db file
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.db_path = db_path
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_round_statistics(self) -> List[Dict[str, Any]]:
        """
        Get per-round metrics statistics (sent, filtered, total)
        
        Returns:
            List of dicts with keys: round, sent, filtered, total, savings_percent
        """
        conn = self._get_connection()
        df = pd.read_sql("""
            SELECT round, 
                   SUM(metrics_sent) as sent, 
                   SUM(metrics_filtered) as filtered,
                   SUM(metrics_sent + metrics_filtered) as total
            FROM round_metrics_stats
            GROUP BY round
            ORDER BY round
        """, conn)
        conn.close()
        
        if df.empty:
            return []
        
        # Calculate savings percentage for each round
        df['savings_percent'] = ((df['filtered'] / df['total']) * 100).fillna(0)
        df['collected'] = df['total']  # For compatibility with dashboard
        
        return df.to_dict('records')
    
    def get_node_statistics(self) -> List[Dict[str, Any]]:
        """
        Get per-node performance statistics
        
        Returns:
            List of dicts with node_id, metrics_collected, metrics_sent, 
            metrics_filtered, bandwidth_saved
        """
        conn = self._get_connection()
        df = pd.read_sql("""
            SELECT node_ip as node_id,
                   SUM(metrics_sent + metrics_filtered) as metrics_collected,
                   SUM(metrics_sent) as metrics_sent,
                   SUM(metrics_filtered) as metrics_filtered
            FROM round_metrics_stats
            GROUP BY node_ip
            ORDER BY node_ip
        """, conn)
        conn.close()
        
        if df.empty:
            return []
        
        # Calculate bandwidth saved percentage
        df['bandwidth_saved'] = ((df['metrics_filtered'] / df['metrics_collected']) * 100).fillna(0)
        
        # Format for dashboard compatibility
        result = []
        for _, row in df.iterrows():
            result.append({
                'node_id': row['node_id'],
                'statistics': {
                    'metrics_collected': int(row['metrics_collected']),
                    'metrics_sent': int(row['metrics_sent']),
                    'metrics_filtered': int(row['metrics_filtered']),
                    'bandwidth_saved': float(row['bandwidth_saved']),
                    'total_rounds': self._get_total_rounds(),
                    'gossip_messages_sent': 0,  # Not tracked in DEmon DB
                    'gossip_messages_received': 0  # Not tracked in DEmon DB
                }
            })
        
        return result
    
    def get_metric_type_distribution(self) -> List[Dict[str, Any]]:
        """
        Get breakdown of metrics by type (cpu, memory, etc.)
        
        Returns:
            List of dicts with metric_type, sent_count, filtered_count, total_count
        """
        conn = self._get_connection()
        
        # Check if metric_transmissions table exists
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='metric_transmissions'
        """)
        
        if not cursor.fetchone():
            conn.close()
            return []
        
        df = pd.read_sql("""
            SELECT metric_type, 
                   SUM(CASE WHEN was_sent = 1 THEN 1 ELSE 0 END) as sent_count,
                   SUM(CASE WHEN was_sent = 0 THEN 1 ELSE 0 END) as filtered_count,
                   COUNT(*) as total_count
            FROM metric_transmissions
            GROUP BY metric_type
        """, conn)
        conn.close()
        
        return df.to_dict('records')
    
    def get_experiment_summary(self) -> Dict[str, Any]:
        """
        Get overall experiment configuration and results summary
        
        Returns:
            Dict with experiment stats including total metrics, bandwidth saved, etc.
        """
        conn = self._get_connection()
        
        # Get aggregated stats
        df = pd.read_sql("""
            SELECT SUM(metrics_sent) as total_sent,
                   SUM(metrics_filtered) as total_filtered,
                   SUM(metrics_sent + metrics_filtered) as total_collected
            FROM round_metrics_stats
        """, conn)
        
        # Get unique node count
        node_df = pd.read_sql("""
            SELECT COUNT(DISTINCT node_ip) as node_count
            FROM round_metrics_stats
        """, conn)
        
        # Get max round
        round_df = pd.read_sql("""
            SELECT MAX(round) as max_round
            FROM round_metrics_stats
        """, conn)
        
        conn.close()
        
        if df.empty:
            return {
                'total_metrics_collected': 0,
                'total_metrics_sent': 0,
                'total_metrics_filtered': 0,
                'average_bandwidth_saved': 0.0,
                'num_nodes': 0,
                'total_rounds': 0
            }
        
        total_sent = int(df['total_sent'][0]) if df['total_sent'][0] else 0
        total_filtered = int(df['total_filtered'][0]) if df['total_filtered'][0] else 0
        total_collected = total_sent + total_filtered
        
        bandwidth_saved = (total_filtered / total_collected * 100) if total_collected > 0 else 0.0
        
        return {
            'total_metrics_collected': total_collected,
            'total_metrics_sent': total_sent,
            'total_metrics_filtered': total_filtered,
            'average_bandwidth_saved': round(bandwidth_saved, 2),
            'num_nodes': int(node_df['node_count'][0]) if not node_df.empty else 0,
            'total_rounds': int(round_df['max_round'][0]) if not round_df.empty and round_df['max_round'][0] else 0
        }
    
    def _get_total_rounds(self) -> int:
        """Helper to get total number of rounds"""
        conn = self._get_connection()
        df = pd.read_sql("SELECT MAX(round) as max_round FROM round_metrics_stats", conn)
        conn.close()
        return int(df['max_round'][0]) if not df.empty and df['max_round'][0] else 0
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get all data needed for dashboard in a single call
        
        Returns:
            Complete dataset for dashboard rendering
        """
        summary = self.get_experiment_summary()
        
        return {
            'experiment_config': {
                'num_nodes': summary['num_nodes'],
                'max_rounds': summary['total_rounds'],
                'voi_enabled': True,  # DEmon always uses VoI
                'gossip_rate': 2.0  # Default from DEmon config
            },
            'experiment_stats': {
                'start_time': None,  # Not tracked in DB
                'end_time': None,  # Not tracked in DB
                'total_rounds': summary['total_rounds'],
                'total_metrics_collected': summary['total_metrics_collected'],
                'total_metrics_sent': summary['total_metrics_sent'],
                'total_metrics_filtered': summary['total_metrics_filtered'],
                'average_bandwidth_saved': summary['average_bandwidth_saved'],
                'round_history': self.get_round_statistics()
            },
            'node_results': self.get_node_statistics(),
            'metric_breakdown': self.get_metric_type_distribution()
        }


if __name__ == "__main__":
    # Test the connector
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python demon_db_connector.py <path_to_demonDB.db>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    try:
        connector = DemonDBConnector(db_path)
        summary = connector.get_experiment_summary()
        
        print("=== DEmon Experiment Summary ===")
        print(f"Nodes: {summary['num_nodes']}")
        print(f"Rounds: {summary['total_rounds']}")
        print(f"Metrics Collected: {summary['total_metrics_collected']}")
        print(f"Metrics Sent: {summary['total_metrics_sent']}")
        print(f"Metrics Filtered: {summary['total_metrics_filtered']}")
        print(f"Bandwidth Saved: {summary['average_bandwidth_saved']:.2f}%")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
