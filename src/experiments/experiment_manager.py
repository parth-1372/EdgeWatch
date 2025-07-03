"""
EdgeWatch Experiment Manager
Comprehensive experiment management and coordination
"""

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import uuid
import logging
from collections import defaultdict
from enum import Enum

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager
from ..monitoring.metrics_collector import MetricsCollector


class ExperimentStatus(Enum):
    """Experiment status values"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentType(Enum):
    """Types of experiments"""
    AB_TEST = "ab_test"
    PERFORMANCE = "performance"
    LOAD_TEST = "load_test"
    CONFIGURATION = "configuration"
    ALGORITHM = "algorithm"


class ExperimentManager:
    """Central experiment management system"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager, 
                 metrics_collector: MetricsCollector):
        self.config = config_manager
        self.db = db_manager
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Experiment storage
        self._active_experiments = {}
        self._experiment_history = []
        self._experiment_callbacks = defaultdict(list)
        
        # Execution
        self._execution_thread = None
        self._running = False
        
        # Configuration
        self.max_concurrent_experiments = self.config.get('experiments.max_concurrent', 5)
        self.default_duration = self.config.get('experiments.default_duration_minutes', 60)
        
    def start_manager(self):
        """Start the experiment manager"""
        if self._running:
            return
            
        self._running = True
        self._execution_thread = threading.Thread(target=self._execution_loop, daemon=True)
        self._execution_thread.start()
        self.logger.info("Experiment manager started")
        
    def stop_manager(self):
        """Stop the experiment manager"""
        self._running = False
        if self._execution_thread:
            self._execution_thread.join(timeout=10)
        self.logger.info("Experiment manager stopped")
        
    def create_experiment(self, name: str, experiment_type: ExperimentType,
                         config: Dict[str, Any], duration_minutes: Optional[int] = None,
                         description: Optional[str] = None) -> str:
        """Create a new experiment"""
        experiment_id = str(uuid.uuid4())
        
        experiment = {
            'id': experiment_id,
            'name': name,
            'type': experiment_type.value,
            'description': description or '',
            'config': config,
            'status': ExperimentStatus.CREATED.value,
            'created_at': datetime.utcnow(),
            'started_at': None,
            'completed_at': None,
            'duration_minutes': duration_minutes or self.default_duration,
            'results': {},
            'metrics': {},
            'error_message': None,
            'progress': 0
        }
        
        # Store experiment
        self._active_experiments[experiment_id] = experiment
        
        try:
            self.db.store_experiment(experiment)
        except Exception as e:
            self.logger.error(f"Failed to store experiment in database: {e}")
            
        self.logger.info(f"Experiment created: {experiment_id} - {name}")
        return experiment_id
        
    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment"""
        if experiment_id not in self._active_experiments:
            self.logger.error(f"Experiment not found: {experiment_id}")
            return False
            
        experiment = self._active_experiments[experiment_id]
        
        # Check if we can start more experiments
        running_count = sum(1 for exp in self._active_experiments.values() 
                          if exp['status'] == ExperimentStatus.RUNNING.value)
        
        if running_count >= self.max_concurrent_experiments:
            self.logger.warning(f"Cannot start experiment {experiment_id}: max concurrent limit reached")
            return False
            
        # Update experiment status
        experiment['status'] = ExperimentStatus.RUNNING.value
        experiment['started_at'] = datetime.utcnow()
        
        try:
            self.db.update_experiment_status(experiment_id, ExperimentStatus.RUNNING.value)
        except Exception as e:
            self.logger.error(f"Failed to update experiment status in database: {e}")
            
        self.logger.info(f"Experiment started: {experiment_id}")
        
        # Execute experiment-specific startup
        self._execute_experiment_start(experiment)
        
        return True
        
    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause a running experiment"""
        if experiment_id not in self._active_experiments:
            return False
            
        experiment = self._active_experiments[experiment_id]
        
        if experiment['status'] != ExperimentStatus.RUNNING.value:
            return False
            
        experiment['status'] = ExperimentStatus.PAUSED.value
        
        try:
            self.db.update_experiment_status(experiment_id, ExperimentStatus.PAUSED.value)
        except Exception as e:
            self.logger.error(f"Failed to update experiment status in database: {e}")
            
        self.logger.info(f"Experiment paused: {experiment_id}")
        return True
        
    def resume_experiment(self, experiment_id: str) -> bool:
        """Resume a paused experiment"""
        if experiment_id not in self._active_experiments:
            return False
            
        experiment = self._active_experiments[experiment_id]
        
        if experiment['status'] != ExperimentStatus.PAUSED.value:
            return False
            
        experiment['status'] = ExperimentStatus.RUNNING.value
        
        try:
            self.db.update_experiment_status(experiment_id, ExperimentStatus.RUNNING.value)
        except Exception as e:
            self.logger.error(f"Failed to update experiment status in database: {e}")
            
        self.logger.info(f"Experiment resumed: {experiment_id}")
        return True
        
    def stop_experiment(self, experiment_id: str, reason: str = "Manually stopped") -> bool:
        """Stop an experiment"""
        if experiment_id not in self._active_experiments:
            return False
            
        experiment = self._active_experiments[experiment_id]
        
        if experiment['status'] in [ExperimentStatus.COMPLETED.value, 
                                  ExperimentStatus.CANCELLED.value,
                                  ExperimentStatus.FAILED.value]:
            return False
            
        experiment['status'] = ExperimentStatus.CANCELLED.value
        experiment['completed_at'] = datetime.utcnow()
        experiment['error_message'] = reason
        
        try:
            self.db.update_experiment_status(experiment_id, ExperimentStatus.CANCELLED.value)
        except Exception as e:
            self.logger.error(f"Failed to update experiment status in database: {e}")
            
        # Execute experiment-specific cleanup
        self._execute_experiment_stop(experiment)
        
        # Move to history
        self._experiment_history.append(experiment.copy())
        del self._active_experiments[experiment_id]
        
        self.logger.info(f"Experiment stopped: {experiment_id} - {reason}")
        return True
        
    def get_experiment(self, experiment_id: str) -> Optional[Dict]:
        """Get experiment details"""
        if experiment_id in self._active_experiments:
            return self._active_experiments[experiment_id].copy()
        
        # Check history
        for exp in self._experiment_history:
            if exp['id'] == experiment_id:
                return exp.copy()
                
        return None
        
    def get_active_experiments(self) -> List[Dict]:
        """Get all active experiments"""
        return list(self._active_experiments.values())
        
    def get_experiment_history(self, limit: int = 50) -> List[Dict]:
        """Get experiment history"""
        return self._experiment_history[-limit:]
        
    def record_experiment_metric(self, experiment_id: str, metric_name: str, 
                                value: Any, timestamp: Optional[datetime] = None):
        """Record a metric for an experiment"""
        if experiment_id not in self._active_experiments:
            return
            
        experiment = self._active_experiments[experiment_id]
        
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        if 'metrics' not in experiment:
            experiment['metrics'] = {}
            
        if metric_name not in experiment['metrics']:
            experiment['metrics'][metric_name] = []
            
        experiment['metrics'][metric_name].append({
            'value': value,
            'timestamp': timestamp
        })
        
        # Also record in main metrics collector
        self.metrics.record_metric(
            f"experiment_{metric_name}",
            value,
            timestamp,
            tags={'experiment_id': experiment_id, 'experiment_type': experiment['type']}
        )
        
    def update_experiment_progress(self, experiment_id: str, progress: float):
        """Update experiment progress (0-100)"""
        if experiment_id not in self._active_experiments:
            return
            
        experiment = self._active_experiments[experiment_id]
        experiment['progress'] = max(0, min(100, progress))
        
    def add_experiment_callback(self, experiment_type: ExperimentType, 
                              callback: Callable[[Dict, str], None]):
        """Add a callback for experiment events"""
        self._experiment_callbacks[experiment_type.value].append(callback)
        
    def _execution_loop(self):
        """Main execution loop for monitoring experiments"""
        while self._running:
            try:
                current_time = datetime.utcnow()
                
                for experiment_id, experiment in list(self._active_experiments.items()):
                    if experiment['status'] == ExperimentStatus.RUNNING.value:
                        # Check if experiment should be completed
                        if self._should_complete_experiment(experiment, current_time):
                            self._complete_experiment(experiment_id)
                            
                        # Update experiment progress
                        self._update_experiment_progress(experiment, current_time)
                        
                        # Execute experiment-specific monitoring
                        self._execute_experiment_monitor(experiment)
                        
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in experiment execution loop: {e}")
                time.sleep(10)
                
    def _should_complete_experiment(self, experiment: Dict, current_time: datetime) -> bool:
        """Check if an experiment should be completed"""
        if not experiment['started_at']:
            return False
            
        duration = timedelta(minutes=experiment['duration_minutes'])
        return current_time - experiment['started_at'] >= duration
        
    def _complete_experiment(self, experiment_id: str):
        """Complete an experiment"""
        experiment = self._active_experiments[experiment_id]
        experiment['status'] = ExperimentStatus.COMPLETED.value
        experiment['completed_at'] = datetime.utcnow()
        experiment['progress'] = 100
        
        try:
            self.db.update_experiment_status(experiment_id, ExperimentStatus.COMPLETED.value)
        except Exception as e:
            self.logger.error(f"Failed to update experiment status in database: {e}")
            
        # Execute experiment-specific completion
        self._execute_experiment_complete(experiment)
        
        # Move to history
        self._experiment_history.append(experiment.copy())
        del self._active_experiments[experiment_id]
        
        self.logger.info(f"Experiment completed: {experiment_id}")
        
    def _update_experiment_progress(self, experiment: Dict, current_time: datetime):
        """Update experiment progress based on time elapsed"""
        if not experiment['started_at']:
            return
            
        elapsed = (current_time - experiment['started_at']).total_seconds()
        total_duration = experiment['duration_minutes'] * 60
        
        progress = min(100, (elapsed / total_duration) * 100)
        experiment['progress'] = progress
        
    def _execute_experiment_start(self, experiment: Dict):
        """Execute experiment-specific start logic"""
        experiment_type = experiment['type']
        
        for callback in self._experiment_callbacks.get(experiment_type, []):
            try:
                callback(experiment, 'start')
            except Exception as e:
                self.logger.error(f"Error in experiment start callback: {e}")
                
    def _execute_experiment_monitor(self, experiment: Dict):
        """Execute experiment-specific monitoring logic"""
        experiment_type = experiment['type']
        
        for callback in self._experiment_callbacks.get(experiment_type, []):
            try:
                callback(experiment, 'monitor')
            except Exception as e:
                self.logger.error(f"Error in experiment monitor callback: {e}")
                
    def _execute_experiment_complete(self, experiment: Dict):
        """Execute experiment-specific completion logic"""
        experiment_type = experiment['type']
        
        for callback in self._experiment_callbacks.get(experiment_type, []):
            try:
                callback(experiment, 'complete')
            except Exception as e:
                self.logger.error(f"Error in experiment complete callback: {e}")
                
    def _execute_experiment_stop(self, experiment: Dict):
        """Execute experiment-specific stop logic"""
        experiment_type = experiment['type']
        
        for callback in self._experiment_callbacks.get(experiment_type, []):
            try:
                callback(experiment, 'stop')
            except Exception as e:
                self.logger.error(f"Error in experiment stop callback: {e}")
                
    def generate_experiment_report(self, experiment_id: str) -> Optional[Dict]:
        """Generate a comprehensive report for an experiment"""
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return None
            
        report = {
            'experiment': experiment,
            'summary': {
                'id': experiment['id'],
                'name': experiment['name'],
                'type': experiment['type'],
                'status': experiment['status'],
                'duration': self._calculate_duration(experiment),
                'success': experiment['status'] == ExperimentStatus.COMPLETED.value
            },
            'metrics_summary': {},
            'conclusions': [],
            'recommendations': []
        }
        
        # Analyze metrics
        if experiment.get('metrics'):
            for metric_name, values in experiment['metrics'].items():
                if values:
                    metric_values = [v['value'] for v in values if isinstance(v['value'], (int, float))]
                    if metric_values:
                        report['metrics_summary'][metric_name] = {
                            'count': len(metric_values),
                            'min': min(metric_values),
                            'max': max(metric_values),
                            'avg': sum(metric_values) / len(metric_values),
                            'latest': metric_values[-1]
                        }
                        
        # Add type-specific analysis
        if experiment['type'] == ExperimentType.AB_TEST.value:
            report['ab_test_analysis'] = self._analyze_ab_test(experiment)
        elif experiment['type'] == ExperimentType.PERFORMANCE.value:
            report['performance_analysis'] = self._analyze_performance_test(experiment)
            
        return report
        
    def _calculate_duration(self, experiment: Dict) -> Optional[float]:
        """Calculate experiment duration in minutes"""
        if not experiment.get('started_at'):
            return None
            
        end_time = experiment.get('completed_at') or datetime.utcnow()
        duration = (end_time - experiment['started_at']).total_seconds() / 60
        return duration
        
    def _analyze_ab_test(self, experiment: Dict) -> Dict:
        """Analyze A/B test results"""
        # Placeholder for A/B test specific analysis
        return {
            'statistical_significance': None,
            'confidence_interval': None,
            'winner': None,
            'improvement': None
        }
        
    def _analyze_performance_test(self, experiment: Dict) -> Dict:
        """Analyze performance test results"""
        # Placeholder for performance test specific analysis
        return {
            'baseline_performance': None,
            'test_performance': None,
            'improvement_percent': None,
            'bottlenecks_identified': []
        }
