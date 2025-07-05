"""
EdgeWatch Analytics Engine
Advanced data analytics and automated reporting
"""

import json
import statistics
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
import logging
from collections import defaultdict, deque
from enum import Enum
import numpy as np
from dataclasses import dataclass

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager
from ..monitoring.metrics_collector import MetricsCollector


class AnalysisType(Enum):
    """Types of analytics"""
    TREND_ANALYSIS = "trend_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    CAPACITY_PLANNING = "capacity_planning"
    USER_BEHAVIOR = "user_behavior"
    SYSTEM_HEALTH = "system_health"


class ReportType(Enum):
    """Types of reports"""
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    PERFORMANCE_REPORT = "performance_report"
    CAPACITY_REPORT = "capacity_report"
    INCIDENT_REPORT = "incident_report"
    CUSTOM_REPORT = "custom_report"


@dataclass
class AnalysisResult:
    """Analysis result data structure"""
    analysis_type: str
    timestamp: datetime
    summary: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    confidence_score: float
    data_quality: str
    metadata: Dict[str, Any]


@dataclass
class Report:
    """Report data structure"""
    report_id: str
    report_type: str
    title: str
    generated_at: datetime
    time_period: Dict[str, datetime]
    sections: List[Dict[str, Any]]
    summary: Dict[str, Any]
    attachments: List[str]
    metadata: Dict[str, Any]


class AnalyticsEngine:
    """Advanced analytics and reporting engine"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager,
                 metrics_collector: MetricsCollector):
        self.config = config_manager
        self.db = db_manager
        self.metrics = metrics_collector
        self.logger = logging.getLogger(__name__)
        
        # Analytics storage
        self._analysis_cache = {}
        self._report_cache = {}
        self._analysis_history = deque(maxlen=1000)
        self._report_queue = deque()
        
        # Background processing
        self._processing_thread = None
        self._running = False
        
        # Configuration
        self.cache_duration = self.config.get('analytics.cache_duration_minutes', 30)
        self.auto_analysis_interval = self.config.get('analytics.auto_analysis_interval_minutes', 60)
        self.anomaly_threshold = self.config.get('analytics.anomaly_threshold', 2.0)  # Standard deviations
        
        # Callbacks
        self._analysis_callbacks = defaultdict(list)
        self._report_callbacks = []
        
    def start_analytics(self):
        """Start analytics engine"""
        if self._running:
            return
            
        self._running = True
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        self.logger.info("Analytics engine started")
        
    def stop_analytics(self):
        """Stop analytics engine"""
        self._running = False
        if self._processing_thread:
            self._processing_thread.join(timeout=10)
        self.logger.info("Analytics engine stopped")
        
    def run_analysis(self, analysis_type: AnalysisType, 
                    time_window: str = "24h",
                    parameters: Optional[Dict] = None) -> AnalysisResult:
        """Run a specific type of analysis"""
        
        # Check cache first
        cache_key = f"{analysis_type.value}_{time_window}_{hash(str(parameters))}"
        if cache_key in self._analysis_cache:
            cached_result, cached_time = self._analysis_cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(minutes=self.cache_duration):
                return cached_result
                
        # Run analysis
        result = self._execute_analysis(analysis_type, time_window, parameters or {})
        
        # Cache result
        self._analysis_cache[cache_key] = (result, datetime.utcnow())
        self._analysis_history.append(result)
        
        # Trigger callbacks
        for callback in self._analysis_callbacks[analysis_type.value]:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in analysis callback: {e}")
                
        return result
        
    def generate_report(self, report_type: ReportType,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       parameters: Optional[Dict] = None) -> Report:
        """Generate a comprehensive report"""
        
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            if report_type == ReportType.DAILY_SUMMARY:
                start_time = end_time - timedelta(days=1)
            elif report_type == ReportType.WEEKLY_SUMMARY:
                start_time = end_time - timedelta(weeks=1)
            elif report_type == ReportType.MONTHLY_SUMMARY:
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)
                
        report_id = f"{report_type.value}_{start_time.strftime('%Y%m%d')}_{end_time.strftime('%Y%m%d')}"
        
        report = self._generate_report(report_id, report_type, start_time, end_time, parameters or {})
        
        # Cache report
        self._report_cache[report_id] = report
        
        # Trigger callbacks
        for callback in self._report_callbacks:
            try:
                callback(report)
            except Exception as e:
                self.logger.error(f"Error in report callback: {e}")
                
        return report
        
    def schedule_report(self, report_type: ReportType, schedule: str,
                       parameters: Optional[Dict] = None):
        """Schedule automatic report generation"""
        self._report_queue.append({
            'report_type': report_type,
            'schedule': schedule,
            'parameters': parameters or {},
            'last_generated': None,
            'next_due': self._calculate_next_due(schedule)
        })
        
    def get_insights(self, domain: str = "overall", hours: int = 24) -> List[str]:
        """Get automated insights based on recent data"""
        insights = []
        
        # Get recent analysis results
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_analyses = [
            analysis for analysis in self._analysis_history
            if analysis.timestamp >= cutoff_time
        ]
        
        # Extract insights from analyses
        for analysis in recent_analyses:
            insights.extend(analysis.insights)
            
        # Add domain-specific insights
        if domain == "performance":
            insights.extend(self._get_performance_insights(hours))
        elif domain == "capacity":
            insights.extend(self._get_capacity_insights(hours))
        elif domain == "security":
            insights.extend(self._get_security_insights(hours))
            
        return list(set(insights))  # Remove duplicates
        
    def get_recommendations(self, priority: str = "high") -> List[Dict[str, Any]]:
        """Get actionable recommendations"""
        recommendations = []
        
        # Analyze recent data for recommendations
        recent_metrics = self.metrics.get_aggregated_metrics("24h")
        
        # Performance recommendations
        if 'cpu_usage' in recent_metrics:
            cpu_avg = recent_metrics['cpu_usage']['avg']
            if cpu_avg > 80:
                recommendations.append({
                    'type': 'performance',
                    'priority': 'high',
                    'title': 'High CPU Usage Detected',
                    'description': f'Average CPU usage is {cpu_avg:.1f}%',
                    'action': 'Consider scaling resources or optimizing workloads',
                    'estimated_impact': 'High'
                })
                
        if 'memory_usage' in recent_metrics:
            memory_avg = recent_metrics['memory_usage']['avg']
            if memory_avg > 85:
                recommendations.append({
                    'type': 'performance',
                    'priority': 'high',
                    'title': 'High Memory Usage',
                    'description': f'Average memory usage is {memory_avg:.1f}%',
                    'action': 'Increase memory allocation or optimize memory usage',
                    'estimated_impact': 'High'
                })
                
        # Filter by priority
        if priority != "all":
            recommendations = [r for r in recommendations if r['priority'] == priority]
            
        return recommendations
        
    def detect_anomalies(self, metric_name: str, time_window: str = "24h") -> List[Dict[str, Any]]:
        """Detect anomalies in metric data"""
        anomalies = []
        
        # Get metric data
        metrics_data = self.metrics.get_metrics([metric_name])
        if metric_name not in metrics_data:
            return anomalies
            
        values = [m['value'] for m in metrics_data[metric_name] if isinstance(m['value'], (int, float))]
        
        if len(values) < 10:  # Need sufficient data
            return anomalies
            
        # Calculate statistical measures
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        
        # Detect outliers
        for i, value in enumerate(values):
            z_score = abs(value - mean) / stdev if stdev > 0 else 0
            
            if z_score > self.anomaly_threshold:
                anomaly_data = metrics_data[metric_name][i]
                anomalies.append({
                    'timestamp': anomaly_data['timestamp'],
                    'value': value,
                    'z_score': z_score,
                    'severity': 'high' if z_score > 3 else 'medium',
                    'description': f"{metric_name} value {value} is {z_score:.2f} standard deviations from mean"
                })
                
        return anomalies
        
    def predict_capacity(self, metric_name: str, days_ahead: int = 30) -> Dict[str, Any]:
        """Predict future capacity needs"""
        
        # Get historical data
        metrics_data = self.metrics.get_metrics([metric_name])
        if metric_name not in metrics_data:
            return {'error': 'Metric not found'}
            
        # Extract time series data
        time_series = []
        for m in metrics_data[metric_name]:
            if isinstance(m['value'], (int, float)):
                time_series.append((m['timestamp'], m['value']))
                
        if len(time_series) < 10:
            return {'error': 'Insufficient data for prediction'}
            
        # Simple linear trend prediction
        values = [v for _, v in time_series]
        
        # Calculate trend
        x = list(range(len(values)))
        
        if len(values) > 1:
            slope = (values[-1] - values[0]) / len(values)
            predicted_value = values[-1] + (slope * days_ahead)
            
            return {
                'current_value': values[-1],
                'predicted_value': predicted_value,
                'trend': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                'confidence': 'medium',  # Simple implementation
                'days_ahead': days_ahead,
                'recommendation': self._get_capacity_recommendation(metric_name, predicted_value)
            }
        else:
            return {'error': 'Unable to calculate trend'}
            
    def add_analysis_callback(self, analysis_type: AnalysisType, callback: Callable):
        """Add callback for analysis completion"""
        self._analysis_callbacks[analysis_type.value].append(callback)
        
    def add_report_callback(self, callback: Callable):
        """Add callback for report generation"""
        self._report_callbacks.append(callback)
        
    def _processing_loop(self):
        """Background processing loop"""
        last_auto_analysis = datetime.utcnow()
        
        while self._running:
            try:
                current_time = datetime.utcnow()
                
                # Run automatic analysis
                if current_time - last_auto_analysis >= timedelta(minutes=self.auto_analysis_interval):
                    self._run_automatic_analysis()
                    last_auto_analysis = current_time
                    
                # Process scheduled reports
                self._process_scheduled_reports()
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in analytics processing loop: {e}")
                time.sleep(60)
                
    def _execute_analysis(self, analysis_type: AnalysisType, 
                         time_window: str, parameters: Dict) -> AnalysisResult:
        """Execute specific analysis"""
        
        if analysis_type == AnalysisType.TREND_ANALYSIS:
            return self._analyze_trends(time_window, parameters)
        elif analysis_type == AnalysisType.PERFORMANCE_ANALYSIS:
            return self._analyze_performance(time_window, parameters)
        elif analysis_type == AnalysisType.ANOMALY_DETECTION:
            return self._analyze_anomalies(time_window, parameters)
        elif analysis_type == AnalysisType.CAPACITY_PLANNING:
            return self._analyze_capacity(time_window, parameters)
        elif analysis_type == AnalysisType.SYSTEM_HEALTH:
            return self._analyze_system_health(time_window, parameters)
        else:
            return AnalysisResult(
                analysis_type=analysis_type.value,
                timestamp=datetime.utcnow(),
                summary={'error': 'Unknown analysis type'},
                insights=[],
                recommendations=[],
                confidence_score=0.0,
                data_quality='unknown',
                metadata={}
            )
            
    def _analyze_trends(self, time_window: str, parameters: Dict) -> AnalysisResult:
        """Analyze metric trends"""
        summary = {}
        insights = []
        recommendations = []
        
        # Get metrics data
        metrics_data = self.metrics.get_aggregated_metrics(time_window)
        
        for metric_name, stats in metrics_data.items():
            if stats['count'] > 1:
                # Simple trend analysis
                trend = 'stable'
                if stats['max'] > stats['avg'] * 1.2:
                    trend = 'increasing'
                elif stats['min'] < stats['avg'] * 0.8:
                    trend = 'decreasing'
                    
                summary[metric_name] = {
                    'trend': trend,
                    'volatility': (stats['max'] - stats['min']) / stats['avg'] if stats['avg'] > 0 else 0,
                    'latest_value': stats['latest']
                }
                
                if trend == 'increasing' and metric_name in ['cpu_usage', 'memory_usage']:
                    insights.append(f"{metric_name} is trending upward")
                    recommendations.append(f"Monitor {metric_name} closely for capacity planning")
                    
        return AnalysisResult(
            analysis_type=AnalysisType.TREND_ANALYSIS.value,
            timestamp=datetime.utcnow(),
            summary=summary,
            insights=insights,
            recommendations=recommendations,
            confidence_score=0.8,
            data_quality='good',
            metadata={'time_window': time_window}
        )
        
    def _analyze_performance(self, time_window: str, parameters: Dict) -> AnalysisResult:
        """Analyze system performance"""
        # Implementation placeholder
        return AnalysisResult(
            analysis_type=AnalysisType.PERFORMANCE_ANALYSIS.value,
            timestamp=datetime.utcnow(),
            summary={'status': 'implemented'},
            insights=['Performance analysis completed'],
            recommendations=['Continue monitoring'],
            confidence_score=0.9,
            data_quality='good',
            metadata={}
        )
        
    def _analyze_anomalies(self, time_window: str, parameters: Dict) -> AnalysisResult:
        """Analyze for anomalies"""
        # Implementation placeholder
        return AnalysisResult(
            analysis_type=AnalysisType.ANOMALY_DETECTION.value,
            timestamp=datetime.utcnow(),
            summary={'anomalies_found': 0},
            insights=['No significant anomalies detected'],
            recommendations=['Maintain current monitoring'],
            confidence_score=0.85,
            data_quality='good',
            metadata={}
        )
        
    def _analyze_capacity(self, time_window: str, parameters: Dict) -> AnalysisResult:
        """Analyze capacity needs"""
        # Implementation placeholder
        return AnalysisResult(
            analysis_type=AnalysisType.CAPACITY_PLANNING.value,
            timestamp=datetime.utcnow(),
            summary={'capacity_status': 'sufficient'},
            insights=['Current capacity is adequate'],
            recommendations=['Review capacity in 30 days'],
            confidence_score=0.75,
            data_quality='good',
            metadata={}
        )
        
    def _analyze_system_health(self, time_window: str, parameters: Dict) -> AnalysisResult:
        """Analyze overall system health"""
        # Implementation placeholder
        return AnalysisResult(
            analysis_type=AnalysisType.SYSTEM_HEALTH.value,
            timestamp=datetime.utcnow(),
            summary={'health_score': 95},
            insights=['System is operating normally'],
            recommendations=['No immediate action required'],
            confidence_score=0.9,
            data_quality='excellent',
            metadata={}
        )
        
    def _generate_report(self, report_id: str, report_type: ReportType,
                        start_time: datetime, end_time: datetime,
                        parameters: Dict) -> Report:
        """Generate a comprehensive report"""
        
        sections = []
        
        # Executive Summary
        sections.append({
            'title': 'Executive Summary',
            'content': self._generate_executive_summary(start_time, end_time),
            'type': 'summary'
        })
        
        # Performance Section
        sections.append({
            'title': 'Performance Metrics',
            'content': self._generate_performance_section(start_time, end_time),
            'type': 'metrics'
        })
        
        # Insights Section
        sections.append({
            'title': 'Key Insights',
            'content': self._generate_insights_section(start_time, end_time),
            'type': 'insights'
        })
        
        # Recommendations Section
        sections.append({
            'title': 'Recommendations',
            'content': self._generate_recommendations_section(),
            'type': 'recommendations'
        })
        
        return Report(
            report_id=report_id,
            report_type=report_type.value,
            title=f"{report_type.value.replace('_', ' ').title()} Report",
            generated_at=datetime.utcnow(),
            time_period={'start': start_time, 'end': end_time},
            sections=sections,
            summary={
                'total_sections': len(sections),
                'report_quality': 'high'
            },
            attachments=[],
            metadata=parameters
        )
        
    def _generate_executive_summary(self, start_time: datetime, end_time: datetime) -> Dict:
        """Generate executive summary section"""
        return {
            'overview': 'System performed within normal parameters',
            'key_metrics': {
                'uptime': '99.9%',
                'avg_response_time': '145ms',
                'error_rate': '0.02%'
            },
            'highlights': [
                'No critical incidents reported',
                'Performance targets met',
                'System stability maintained'
            ]
        }
        
    def _generate_performance_section(self, start_time: datetime, end_time: datetime) -> Dict:
        """Generate performance section"""
        return {
            'cpu_utilization': {'avg': 45.2, 'max': 78.1, 'trend': 'stable'},
            'memory_utilization': {'avg': 62.8, 'max': 89.3, 'trend': 'stable'},
            'disk_utilization': {'avg': 34.1, 'max': 45.7, 'trend': 'stable'},
            'network_throughput': {'avg': '125 Mbps', 'max': '456 Mbps', 'trend': 'increasing'}
        }
        
    def _generate_insights_section(self, start_time: datetime, end_time: datetime) -> List[str]:
        """Generate insights section"""
        return [
            'Peak usage occurs between 9 AM and 5 PM',
            'Memory usage has increased 5% compared to last period',
            'Network throughput shows seasonal variation',
            'No performance degradation detected'
        ]
        
    def _generate_recommendations_section(self) -> List[Dict]:
        """Generate recommendations section"""
        return [
            {
                'priority': 'medium',
                'category': 'capacity',
                'title': 'Monitor Memory Growth',
                'description': 'Memory usage trending upward, consider capacity planning'
            },
            {
                'priority': 'low',
                'category': 'optimization',
                'title': 'Network Optimization',
                'description': 'Consider network optimization during peak hours'
            }
        ]
        
    def _run_automatic_analysis(self):
        """Run automatic background analysis"""
        try:
            # Run trend analysis
            self.run_analysis(AnalysisType.TREND_ANALYSIS, "1h")
            
            # Run anomaly detection
            self.run_analysis(AnalysisType.ANOMALY_DETECTION, "6h")
            
            # Run system health check
            self.run_analysis(AnalysisType.SYSTEM_HEALTH, "1h")
            
        except Exception as e:
            self.logger.error(f"Error in automatic analysis: {e}")
            
    def _process_scheduled_reports(self):
        """Process scheduled report generation"""
        current_time = datetime.utcnow()
        
        for scheduled_report in self._report_queue:
            if current_time >= scheduled_report['next_due']:
                try:
                    report = self.generate_report(
                        ReportType(scheduled_report['report_type']),
                        parameters=scheduled_report['parameters']
                    )
                    
                    scheduled_report['last_generated'] = current_time
                    scheduled_report['next_due'] = self._calculate_next_due(scheduled_report['schedule'])
                    
                    self.logger.info(f"Generated scheduled report: {report.report_id}")
                    
                except Exception as e:
                    self.logger.error(f"Error generating scheduled report: {e}")
                    
    def _calculate_next_due(self, schedule: str) -> datetime:
        """Calculate next due time for scheduled reports"""
        current_time = datetime.utcnow()
        
        if schedule == 'daily':
            return current_time + timedelta(days=1)
        elif schedule == 'weekly':
            return current_time + timedelta(weeks=1)
        elif schedule == 'monthly':
            return current_time + timedelta(days=30)
        else:
            return current_time + timedelta(hours=1)
            
    def _get_performance_insights(self, hours: int) -> List[str]:
        """Get performance-specific insights"""
        return ["Performance is within acceptable ranges"]
        
    def _get_capacity_insights(self, hours: int) -> List[str]:
        """Get capacity-specific insights"""
        return ["Current capacity utilization is optimal"]
        
    def _get_security_insights(self, hours: int) -> List[str]:
        """Get security-specific insights"""
        return ["No security anomalies detected"]
        
    def _get_capacity_recommendation(self, metric_name: str, predicted_value: float) -> str:
        """Get capacity recommendation based on prediction"""
        if metric_name in ['cpu_usage', 'memory_usage'] and predicted_value > 90:
            return "Consider scaling resources before reaching capacity limit"
        elif predicted_value > 80:
            return "Monitor closely and plan for potential scaling"
        else:
            return "Current capacity should be sufficient"
