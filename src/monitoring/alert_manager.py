"""
EdgeWatch Alert Manager
Comprehensive alerting and notification system
"""

import smtplib
import json
import requests
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from collections import defaultdict, deque
from enum import Enum

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertManager:
    """Comprehensive alert management system"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Alert storage
        self._active_alerts = {}
        self._alert_history = deque(maxlen=10000)
        self._suppressed_alerts = defaultdict(datetime)
        
        # Configuration
        self.notification_channels = self._load_notification_config()
        self.alert_rules = self._load_alert_rules()
        self.suppression_time = self.config.get('alerts.suppression_minutes', 15)
        
        # Processing
        self._processing_thread = None
        self._running = False
        self._alert_queue = deque()
        self._alert_callbacks = []
        
    def start_processing(self):
        """Start alert processing"""
        if self._running:
            return
            
        self._running = True
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        self.logger.info("Alert processing started")
        
    def stop_processing(self):
        """Stop alert processing"""
        self._running = False
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
        self.logger.info("Alert processing stopped")
        
    def create_alert(self, alert_type: str, message: str, severity: AlertSeverity,
                    source: str, details: Optional[Dict] = None,
                    suppress_duplicate: bool = True) -> str:
        """Create a new alert"""
        alert_id = f"{alert_type}_{source}_{int(time.time())}"
        
        # Check for suppression
        if suppress_duplicate:
            suppression_key = f"{alert_type}_{source}"
            if (suppression_key in self._suppressed_alerts and 
                datetime.utcnow() - self._suppressed_alerts[suppression_key] < timedelta(minutes=self.suppression_time)):
                self.logger.debug(f"Alert suppressed: {suppression_key}")
                return alert_id
                
        alert = {
            'id': alert_id,
            'type': alert_type,
            'message': message,
            'severity': severity.value,
            'source': source,
            'details': details or {},
            'status': AlertStatus.ACTIVE.value,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'acknowledged_by': None,
            'acknowledged_at': None,
            'resolved_at': None
        }
        
        # Store alert
        self._active_alerts[alert_id] = alert
        self._alert_history.append(alert.copy())
        
        # Add to processing queue
        self._alert_queue.append(alert)
        
        # Update suppression
        if suppress_duplicate:
            suppression_key = f"{alert_type}_{source}"
            self._suppressed_alerts[suppression_key] = datetime.utcnow()
            
        # Store in database
        try:
            self.db.store_alert(alert)
        except Exception as e:
            self.logger.error(f"Failed to store alert in database: {e}")
            
        self.logger.info(f"Alert created: {alert_id} - {message}")
        return alert_id
        
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self._active_alerts:
            return False
            
        alert = self._active_alerts[alert_id]
        alert['status'] = AlertStatus.ACKNOWLEDGED.value
        alert['acknowledged_by'] = acknowledged_by
        alert['acknowledged_at'] = datetime.utcnow()
        alert['updated_at'] = datetime.utcnow()
        
        try:
            self.db.update_alert_status(alert_id, AlertStatus.ACKNOWLEDGED.value, 
                                      acknowledged_by=acknowledged_by)
        except Exception as e:
            self.logger.error(f"Failed to update alert in database: {e}")
            
        self.logger.info(f"Alert acknowledged: {alert_id} by {acknowledged_by}")
        return True
        
    def resolve_alert(self, alert_id: str, resolved_by: Optional[str] = None) -> bool:
        """Resolve an alert"""
        if alert_id not in self._active_alerts:
            return False
            
        alert = self._active_alerts[alert_id]
        alert['status'] = AlertStatus.RESOLVED.value
        alert['resolved_at'] = datetime.utcnow()
        alert['updated_at'] = datetime.utcnow()
        
        # Remove from active alerts
        del self._active_alerts[alert_id]
        
        try:
            self.db.update_alert_status(alert_id, AlertStatus.RESOLVED.value)
        except Exception as e:
            self.logger.error(f"Failed to update alert in database: {e}")
            
        self.logger.info(f"Alert resolved: {alert_id}")
        return True
        
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Dict]:
        """Get all active alerts"""
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [alert for alert in alerts if alert['severity'] == severity.value]
            
        # Sort by severity and creation time
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: (severity_order.get(x['severity'], 3), x['created_at']))
        
        return alerts
        
    def get_alert_history(self, limit: int = 100, 
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[Dict]:
        """Get alert history"""
        history = list(self._alert_history)
        
        # Filter by time range
        if start_time or end_time:
            filtered_history = []
            for alert in history:
                created_at = alert['created_at']
                if start_time and created_at < start_time:
                    continue
                if end_time and created_at > end_time:
                    continue
                filtered_history.append(alert)
            history = filtered_history
            
        # Sort by creation time (newest first) and limit
        history.sort(key=lambda x: x['created_at'], reverse=True)
        return history[:limit]
        
    def get_alert_stats(self, time_window: str = '24h') -> Dict[str, Any]:
        """Get alert statistics"""
        window_seconds = self._parse_time_window(time_window)
        cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        recent_alerts = [
            alert for alert in self._alert_history
            if alert['created_at'] >= cutoff_time
        ]
        
        stats = {
            'total_alerts': len(recent_alerts),
            'active_alerts': len(self._active_alerts),
            'by_severity': defaultdict(int),
            'by_type': defaultdict(int),
            'by_source': defaultdict(int),
            'resolution_rate': 0,
            'avg_resolution_time': 0
        }
        
        resolved_alerts = []
        resolution_times = []
        
        for alert in recent_alerts:
            stats['by_severity'][alert['severity']] += 1
            stats['by_type'][alert['type']] += 1
            stats['by_source'][alert['source']] += 1
            
            if alert['status'] == AlertStatus.RESOLVED.value:
                resolved_alerts.append(alert)
                if alert.get('resolved_at'):
                    resolution_time = (alert['resolved_at'] - alert['created_at']).total_seconds()
                    resolution_times.append(resolution_time)
                    
        if len(recent_alerts) > 0:
            stats['resolution_rate'] = len(resolved_alerts) / len(recent_alerts)
            
        if resolution_times:
            stats['avg_resolution_time'] = sum(resolution_times) / len(resolution_times)
            
        return stats
        
    def add_notification_callback(self, callback: Callable[[Dict], None]):
        """Add a callback for alert notifications"""
        self._alert_callbacks.append(callback)
        
    def _processing_loop(self):
        """Main alert processing loop"""
        while self._running:
            try:
                # Process queued alerts
                while self._alert_queue:
                    alert = self._alert_queue.popleft()
                    self._process_alert(alert)
                    
                # Check for alert escalations
                self._check_escalations()
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in alert processing: {e}")
                time.sleep(5)
                
    def _process_alert(self, alert: Dict):
        """Process a single alert"""
        try:
            # Send notifications based on severity and rules
            severity = AlertSeverity(alert['severity'])
            
            # Determine which channels to use
            channels = self._get_notification_channels(alert)
            
            for channel in channels:
                self._send_notification(alert, channel)
                
            # Call registered callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error processing alert {alert['id']}: {e}")
            
    def _get_notification_channels(self, alert: Dict) -> List[str]:
        """Determine which notification channels to use for an alert"""
        channels = []
        severity = alert['severity']
        alert_type = alert['type']
        
        # Check alert rules
        for rule in self.alert_rules:
            if self._matches_rule(alert, rule):
                channels.extend(rule.get('channels', []))
                
        # Default channels based on severity
        if not channels:
            if severity == AlertSeverity.CRITICAL.value:
                channels = ['email', 'webhook']
            elif severity == AlertSeverity.WARNING.value:
                channels = ['email']
            else:
                channels = ['webhook']
                
        return list(set(channels))  # Remove duplicates
        
    def _matches_rule(self, alert: Dict, rule: Dict) -> bool:
        """Check if an alert matches a notification rule"""
        # Check severity
        if 'severity' in rule and alert['severity'] not in rule['severity']:
            return False
            
        # Check alert type
        if 'type' in rule and alert['type'] not in rule['type']:
            return False
            
        # Check source
        if 'source' in rule and alert['source'] not in rule['source']:
            return False
            
        return True
        
    def _send_notification(self, alert: Dict, channel: str):
        """Send notification through specified channel"""
        try:
            if channel == 'email':
                self._send_email_notification(alert)
            elif channel == 'webhook':
                self._send_webhook_notification(alert)
            elif channel == 'sms':
                self._send_sms_notification(alert)
            else:
                self.logger.warning(f"Unknown notification channel: {channel}")
                
        except Exception as e:
            self.logger.error(f"Failed to send {channel} notification: {e}")
            
    def _send_email_notification(self, alert: Dict):
        """Send email notification"""
        email_config = self.notification_channels.get('email', {})
        if not email_config.get('enabled', False):
            return
            
        smtp_server = email_config.get('smtp_server')
        smtp_port = email_config.get('smtp_port', 587)
        username = email_config.get('username')
        password = email_config.get('password')
        to_addresses = email_config.get('to_addresses', [])
        
        if not all([smtp_server, username, password, to_addresses]):
            self.logger.warning("Email configuration incomplete")
            return
            
        subject = f"EdgeWatch Alert: {alert['type']} - {alert['severity'].upper()}"
        
        body = f"""
EdgeWatch Alert Notification

Alert ID: {alert['id']}
Type: {alert['type']}
Severity: {alert['severity'].upper()}
Source: {alert['source']}
Message: {alert['message']}
Created: {alert['created_at']}

Details:
{json.dumps(alert['details'], indent=2)}
"""
        
        msg = MIMEMultipart()
        msg['From'] = username
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            
            for to_address in to_addresses:
                msg['To'] = to_address
                server.send_message(msg)
                del msg['To']
                
    def _send_webhook_notification(self, alert: Dict):
        """Send webhook notification"""
        webhook_config = self.notification_channels.get('webhook', {})
        if not webhook_config.get('enabled', False):
            return
            
        url = webhook_config.get('url')
        headers = webhook_config.get('headers', {})
        
        if not url:
            self.logger.warning("Webhook URL not configured")
            return
            
        payload = {
            'alert_id': alert['id'],
            'type': alert['type'],
            'severity': alert['severity'],
            'source': alert['source'],
            'message': alert['message'],
            'created_at': alert['created_at'].isoformat(),
            'details': alert['details']
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
    def _send_sms_notification(self, alert: Dict):
        """Send SMS notification (placeholder)"""
        # This would integrate with SMS services like Twilio
        self.logger.info(f"SMS notification for alert {alert['id']} (not implemented)")
        
    def _check_escalations(self):
        """Check for alerts that need escalation"""
        escalation_time = timedelta(minutes=self.config.get('alerts.escalation_minutes', 30))
        current_time = datetime.utcnow()
        
        for alert in self._active_alerts.values():
            if (alert['status'] == AlertStatus.ACTIVE.value and 
                alert['severity'] == AlertSeverity.CRITICAL.value and
                current_time - alert['created_at'] > escalation_time):
                
                # Escalate alert
                self._escalate_alert(alert)
                
    def _escalate_alert(self, alert: Dict):
        """Escalate an alert"""
        escalation_message = f"ESCALATED: {alert['message']}"
        
        # Send escalation notifications
        escalation_channels = self.notification_channels.get('escalation', ['email'])
        for channel in escalation_channels:
            escalated_alert = alert.copy()
            escalated_alert['message'] = escalation_message
            escalated_alert['escalated'] = True
            self._send_notification(escalated_alert, channel)
            
        self.logger.warning(f"Alert escalated: {alert['id']}")
        
    def _load_notification_config(self) -> Dict:
        """Load notification channel configuration"""
        return {
            'email': {
                'enabled': self.config.get('notifications.email.enabled', False),
                'smtp_server': self.config.get('notifications.email.smtp_server'),
                'smtp_port': self.config.get('notifications.email.smtp_port', 587),
                'username': self.config.get('notifications.email.username'),
                'password': self.config.get('notifications.email.password'),
                'to_addresses': self.config.get('notifications.email.to_addresses', [])
            },
            'webhook': {
                'enabled': self.config.get('notifications.webhook.enabled', False),
                'url': self.config.get('notifications.webhook.url'),
                'headers': self.config.get('notifications.webhook.headers', {})
            },
            'sms': {
                'enabled': self.config.get('notifications.sms.enabled', False)
            }
        }
        
    def _load_alert_rules(self) -> List[Dict]:
        """Load alert notification rules"""
        return self.config.get('alerts.rules', [])
        
    def _parse_time_window(self, window: str) -> int:
        """Parse time window string to seconds"""
        if window.endswith('s'):
            return int(window[:-1])
        elif window.endswith('m'):
            return int(window[:-1]) * 60
        elif window.endswith('h'):
            return int(window[:-1]) * 3600
        elif window.endswith('d'):
            return int(window[:-1]) * 86400
        else:
            return int(window)
