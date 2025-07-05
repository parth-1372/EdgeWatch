"""
EdgeWatch Structured Logging and Audit Trail System
Professional logging with correlation IDs and comprehensive audit capabilities
"""

import json
import logging
import threading
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
import contextvars
from collections import deque

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager

# Context variable for correlation ID
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar('correlation_id', default='')

class LogLevel(Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AuditEventType(Enum):
    """Types of audit events"""
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    API_REQUEST = "api_request"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    EXPERIMENT_EVENT = "experiment_event"
    MONITORING_EVENT = "monitoring_event"

@dataclass
class AuditEvent:
    """Audit event data structure"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    correlation_id: str
    user_id: Optional[str]
    resource: str
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        # Create structured log entry
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add correlation ID if available
        corr_id = correlation_id.get()
        if corr_id:
            log_data['correlation_id'] = corr_id
            
        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
            
        return json.dumps(log_data, default=str)

class StructuredLogger:
    """Enhanced logging with structured data and correlation IDs"""
    
    def __init__(self, name: str, config: ConfigManager):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup structured logging configuration"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        formatter = StructuredFormatter()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for application logs
        log_file = self.config.get('logging.file', 'logs/edgewatch.log')
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not setup file logging: {e}")
                
        # Set log level
        log_level = self.config.get('logging.level', 'INFO')
        self.logger.setLevel(getattr(logging, log_level))
        
    def _log_with_context(self, level: LogLevel, message: str, **kwargs):
        """Log message with correlation context"""
        # Create extra fields for structured logging
        extra_fields = {
            'correlation_id': correlation_id.get() or '',
            **kwargs
        }
        
        # Create a custom LogRecord with extra fields
        record = self.logger.makeRecord(
            self.logger.name,
            getattr(logging, level.value),
            '',  # pathname
            0,   # lineno
            message,
            (),  # args
            None,  # exc_info
        )
        record.extra_fields = extra_fields
        
        self.logger.handle(record)
        
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log_with_context(LogLevel.DEBUG, message, **kwargs)
        
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log_with_context(LogLevel.INFO, message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log_with_context(LogLevel.WARNING, message, **kwargs)
        
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log_with_context(LogLevel.ERROR, message, **kwargs)
        
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log_with_context(LogLevel.CRITICAL, message, **kwargs)

class AuditTrail:
    """Comprehensive audit trail system"""
    
    def __init__(self, config: ConfigManager, db_manager: DatabaseManager):
        self.config = config
        self.db = db_manager
        self.logger = StructuredLogger('edgewatch.audit', config)
        
        # In-memory audit event storage
        self.events = deque(maxlen=10000)  # Keep last 10k events in memory
        self._lock = threading.Lock()
        
        # Configuration
        self.enabled = self.config.get('audit.enabled', True)
        self.persist_events = self.config.get('audit.persist_to_database', True)
        self.retention_days = self.config.get('audit.retention_days', 90)
        
    def log_event(self, event_type: AuditEventType, resource: str, action: str, 
                  details: Dict[str, Any], user_id: Optional[str] = None,
                  ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                  success: bool = True, error_message: Optional[str] = None,
                  duration_ms: Optional[float] = None):
        """Log an audit event"""
        
        if not self.enabled:
            return
            
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id.get() or str(uuid.uuid4()),
            user_id=user_id,
            resource=resource,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms
        )
        
        # Store in memory
        with self._lock:
            self.events.append(event)
            
        # Log the audit event
        self.logger.info(
            f"Audit: {action} on {resource}",
            event_type=event_type.value,
            event_id=event.event_id,
            user_id=user_id,
            resource=resource,
            action=action,
            success=success,
            duration_ms=duration_ms,
            details=details
        )
        
    def get_events(self, limit: int = 100, event_type: Optional[AuditEventType] = None,
                   user_id: Optional[str] = None, resource: Optional[str] = None,
                   start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[AuditEvent]:
        """Retrieve audit events with filtering"""
        
        with self._lock:
            filtered_events = list(self.events)
            
        # Apply filters
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        if user_id:
            filtered_events = [e for e in filtered_events if e.user_id == user_id]
        if resource:
            filtered_events = [e for e in filtered_events if resource.lower() in e.resource.lower()]
        if start_time:
            filtered_events = [e for e in filtered_events if e.timestamp >= start_time]
        if end_time:
            filtered_events = [e for e in filtered_events if e.timestamp <= end_time]
            
        # Sort by timestamp (newest first) and limit
        filtered_events.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered_events[:limit]

class CorrelationContext:
    """Context manager for correlation ID"""
    
    def __init__(self, correlation_id_value: Optional[str] = None):
        self.correlation_id_value = correlation_id_value or str(uuid.uuid4())
        self.token = None
        
    def __enter__(self):
        self.token = correlation_id.set(self.correlation_id_value)
        return self.correlation_id_value
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            correlation_id.reset(self.token)

# Global instances
audit_trail: Optional[AuditTrail] = None

def initialize_logging_system(config: ConfigManager, db_manager: DatabaseManager):
    """Initialize global logging and audit system"""
    global audit_trail
    audit_trail = AuditTrail(config, db_manager)

def log_user_action(action: str, resource: str, details: Dict[str, Any], 
                   user_id: Optional[str] = None, **kwargs):
    """Log user action to audit trail"""
    if audit_trail:
        audit_trail.log_event(
            AuditEventType.USER_ACTION, resource, action, details,
            user_id=user_id, **kwargs
        )
