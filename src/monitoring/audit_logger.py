"""
EdgeWatch Audit Logger
Comprehensive audit trail and structured logging system
"""

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import gzip
import os
from collections import deque
import contextvars

from ..core.config_manager import ConfigManager
from ..storage.database import DatabaseManager


class AuditLevel(Enum):
    """Audit event levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SECURITY = "security"
    ADMIN = "admin"


class AuditCategory(Enum):
    """Audit event categories"""
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    API_REQUEST = "api_request"
    DATABASE_OPERATION = "database_operation"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    MONITORING_EVENT = "monitoring_event"


# Context variable for correlation IDs
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)


class AuditLogger:
    """Comprehensive audit logging and trail system"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Audit storage
        self._audit_buffer = deque(maxlen=10000)
        self._session_contexts = {}
        
        # Configuration
        self.enable_database_storage = self.config.get('audit.enable_database', True)
        self.enable_file_storage = self.config.get('audit.enable_file', True)
        self.log_directory = self.config.get('audit.log_directory', '/app/logs/audit')
        self.max_file_size = self.config.get('audit.max_file_size_mb', 100) * 1024 * 1024
        self.compress_old_files = self.config.get('audit.compress_old_files', True)
        self.retention_days = self.config.get('audit.retention_days', 90)
        
        # File logging
        self._current_log_file = None
        self._log_file_lock = threading.Lock()
        
        # Background processing
        self._processing_thread = None
        self._running = False
        
        # Setup
        self._setup_audit_logging()
        
    def start_audit_logging(self):
        """Start audit logging service"""
        if self._running:
            return
            
        self._running = True
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        
        # Create log directory if needed
        if self.enable_file_storage:
            os.makedirs(self.log_directory, exist_ok=True)
            
        self.logger.info("Audit logging started")
        
    def stop_audit_logging(self):
        """Stop audit logging service"""
        self._running = False
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
            
        # Flush remaining audit entries
        self._flush_audit_buffer()
        
        self.logger.info("Audit logging stopped")
        
    def log_audit(self, category: AuditCategory, level: AuditLevel, 
                  event: str, details: Optional[Dict] = None,
                  user_id: Optional[str] = None, session_id: Optional[str] = None,
                  ip_address: Optional[str] = None, correlation_id: Optional[str] = None):
        """Log an audit event"""
        
        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = correlation_id_var.get() or str(uuid.uuid4())
            
        audit_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow(),
            'category': category.value,
            'level': level.value,
            'event': event,
            'details': details or {},
            'user_id': user_id,
            'session_id': session_id,
            'ip_address': ip_address,
            'correlation_id': correlation_id,
            'node_id': self.config.get('node.id', 'unknown'),
            'environment': self.config.get('environment', 'production')
        }
        
        # Add to buffer for processing
        self._audit_buffer.append(audit_entry)
        
        # Log to standard logger as well
        log_level = getattr(logging, level.value.upper(), logging.INFO)
        self.logger.log(log_level, f"AUDIT [{category.value}]: {event}", extra={
            'audit_entry': audit_entry
        })
        
    def log_user_action(self, action: str, user_id: str, session_id: Optional[str] = None,
                       ip_address: Optional[str] = None, details: Optional[Dict] = None):
        """Log a user action"""
        self.log_audit(
            AuditCategory.USER_ACTION,
            AuditLevel.INFO,
            action,
            details=details,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        
    def log_system_event(self, event: str, level: AuditLevel = AuditLevel.INFO,
                        details: Optional[Dict] = None):
        """Log a system event"""
        self.log_audit(
            AuditCategory.SYSTEM_EVENT,
            level,
            event,
            details=details
        )
        
    def log_api_request(self, method: str, endpoint: str, status_code: int,
                       user_id: Optional[str] = None, ip_address: Optional[str] = None,
                       duration: Optional[float] = None, request_size: Optional[int] = None,
                       response_size: Optional[int] = None):
        """Log an API request"""
        details = {
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration_ms': duration * 1000 if duration else None,
            'request_size_bytes': request_size,
            'response_size_bytes': response_size
        }
        
        level = AuditLevel.ERROR if status_code >= 500 else AuditLevel.WARNING if status_code >= 400 else AuditLevel.INFO
        
        self.log_audit(
            AuditCategory.API_REQUEST,
            level,
            f"API request: {method} {endpoint}",
            details=details,
            user_id=user_id,
            ip_address=ip_address
        )
        
    def log_database_operation(self, operation: str, table: Optional[str] = None,
                             affected_rows: Optional[int] = None,
                             duration: Optional[float] = None,
                             user_id: Optional[str] = None):
        """Log a database operation"""
        details = {
            'operation': operation,
            'table': table,
            'affected_rows': affected_rows,
            'duration_ms': duration * 1000 if duration else None
        }
        
        self.log_audit(
            AuditCategory.DATABASE_OPERATION,
            AuditLevel.INFO,
            f"Database operation: {operation}",
            details=details,
            user_id=user_id
        )
        
    def log_configuration_change(self, setting: str, old_value: Any, new_value: Any,
                                user_id: str, session_id: Optional[str] = None):
        """Log a configuration change"""
        details = {
            'setting': setting,
            'old_value': str(old_value),
            'new_value': str(new_value)
        }
        
        self.log_audit(
            AuditCategory.CONFIGURATION_CHANGE,
            AuditLevel.ADMIN,
            f"Configuration changed: {setting}",
            details=details,
            user_id=user_id,
            session_id=session_id
        )
        
    def log_security_event(self, event: str, level: AuditLevel = AuditLevel.SECURITY,
                          user_id: Optional[str] = None, ip_address: Optional[str] = None,
                          details: Optional[Dict] = None):
        """Log a security event"""
        self.log_audit(
            AuditCategory.SECURITY_EVENT,
            level,
            event,
            details=details,
            user_id=user_id,
            ip_address=ip_address
        )
        
    def create_session_context(self, session_id: str, user_id: str, ip_address: str) -> Dict:
        """Create a session context for tracking"""
        context = {
            'session_id': session_id,
            'user_id': user_id,
            'ip_address': ip_address,
            'created_at': datetime.utcnow(),
            'last_activity': datetime.utcnow()
        }
        
        self._session_contexts[session_id] = context
        
        self.log_user_action(
            "Session started",
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        
        return context
        
    def update_session_activity(self, session_id: str):
        """Update session last activity"""
        if session_id in self._session_contexts:
            self._session_contexts[session_id]['last_activity'] = datetime.utcnow()
            
    def end_session_context(self, session_id: str):
        """End a session context"""
        if session_id in self._session_contexts:
            context = self._session_contexts[session_id]
            duration = (datetime.utcnow() - context['created_at']).total_seconds()
            
            self.log_user_action(
                "Session ended",
                user_id=context['user_id'],
                session_id=session_id,
                ip_address=context['ip_address'],
                details={'duration_seconds': duration}
            )
            
            del self._session_contexts[session_id]
            
    def search_audit_logs(self, filters: Optional[Dict] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         limit: int = 100) -> List[Dict]:
        """Search audit logs"""
        
        # Search in memory buffer first
        results = []
        for entry in self._audit_buffer:
            if self._matches_filters(entry, filters, start_time, end_time):
                results.append(entry.copy())
                if len(results) >= limit:
                    break
                    
        # If database storage is enabled, search there too
        if self.enable_database_storage and len(results) < limit:
            try:
                db_results = self.db.search_audit_logs(filters, start_time, end_time, limit - len(results))
                results.extend(db_results)
            except Exception as e:
                self.logger.error(f"Error searching database audit logs: {e}")
                
        return results[:limit]
        
    def get_audit_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit log statistics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        stats = {
            'total_events': 0,
            'by_category': {},
            'by_level': {},
            'by_user': {},
            'by_hour': {},
            'recent_events': []
        }
        
        for entry in self._audit_buffer:
            if entry['timestamp'] >= cutoff_time:
                stats['total_events'] += 1
                
                # By category
                category = entry['category']
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
                
                # By level
                level = entry['level']
                stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
                
                # By user
                user_id = entry.get('user_id', 'system')
                stats['by_user'][user_id] = stats['by_user'].get(user_id, 0) + 1
                
                # By hour
                hour_key = entry['timestamp'].strftime('%Y-%m-%d %H:00')
                stats['by_hour'][hour_key] = stats['by_hour'].get(hour_key, 0) + 1
                
        # Get recent events (last 10)
        recent_entries = [entry for entry in self._audit_buffer if entry['timestamp'] >= cutoff_time]
        stats['recent_events'] = sorted(recent_entries, key=lambda x: x['timestamp'], reverse=True)[:10]
        
        return stats
        
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current context"""
        correlation_id_var.set(correlation_id)
        
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID"""
        return correlation_id_var.get()
        
    def _processing_loop(self):
        """Background processing loop for audit entries"""
        while self._running:
            try:
                self._process_audit_buffer()
                self._cleanup_old_logs()
                time.sleep(5)  # Process every 5 seconds
            except Exception as e:
                self.logger.error(f"Error in audit processing loop: {e}")
                time.sleep(5)
                
    def _process_audit_buffer(self):
        """Process audit entries from buffer"""
        if not self._audit_buffer:
            return
            
        # Get entries to process (up to 100 at a time)
        entries_to_process = []
        for _ in range(min(100, len(self._audit_buffer))):
            if self._audit_buffer:
                entries_to_process.append(self._audit_buffer.popleft())
                
        if not entries_to_process:
            return
            
        # Store in database
        if self.enable_database_storage:
            try:
                self.db.store_audit_entries(entries_to_process)
            except Exception as e:
                self.logger.error(f"Error storing audit entries in database: {e}")
                # Put entries back in buffer
                for entry in reversed(entries_to_process):
                    self._audit_buffer.appendleft(entry)
                return
                
        # Store in file
        if self.enable_file_storage:
            try:
                self._write_to_file(entries_to_process)
            except Exception as e:
                self.logger.error(f"Error writing audit entries to file: {e}")
                
    def _write_to_file(self, entries: List[Dict]):
        """Write audit entries to file"""
        with self._log_file_lock:
            if not self._current_log_file or self._should_rotate_file():
                self._rotate_log_file()
                
            with open(self._current_log_file, 'a', encoding='utf-8') as f:
                for entry in entries:
                    # Convert datetime to ISO format for JSON serialization
                    entry_copy = entry.copy()
                    entry_copy['timestamp'] = entry_copy['timestamp'].isoformat()
                    
                    f.write(json.dumps(entry_copy) + '\n')
                    
    def _should_rotate_file(self) -> bool:
        """Check if log file should be rotated"""
        if not self._current_log_file or not os.path.exists(self._current_log_file):
            return True
            
        file_size = os.path.getsize(self._current_log_file)
        return file_size >= self.max_file_size
        
    def _rotate_log_file(self):
        """Rotate log file"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        # Compress old file if exists
        if self._current_log_file and os.path.exists(self._current_log_file) and self.compress_old_files:
            try:
                compressed_file = f"{self._current_log_file}.gz"
                with open(self._current_log_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        f_out.writelines(f_in)
                        
                os.remove(self._current_log_file)
                self.logger.info(f"Compressed audit log file: {compressed_file}")
            except Exception as e:
                self.logger.error(f"Error compressing audit log file: {e}")
                
        # Create new log file
        self._current_log_file = os.path.join(self.log_directory, f"audit_{timestamp}.log")
        
    def _cleanup_old_logs(self):
        """Clean up old log files"""
        if not self.enable_file_storage:
            return
            
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            for filename in os.listdir(self.log_directory):
                filepath = os.path.join(self.log_directory, filename)
                
                if os.path.isfile(filepath) and filename.startswith('audit_'):
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if file_mtime < cutoff_date:
                        os.remove(filepath)
                        self.logger.info(f"Removed old audit log file: {filename}")
                        
        except Exception as e:
            self.logger.error(f"Error cleaning up old audit logs: {e}")
            
    def _flush_audit_buffer(self):
        """Flush remaining audit entries"""
        if self._audit_buffer:
            self._process_audit_buffer()
            
    def _matches_filters(self, entry: Dict, filters: Optional[Dict],
                        start_time: Optional[datetime], end_time: Optional[datetime]) -> bool:
        """Check if entry matches search filters"""
        
        # Time range filter
        if start_time and entry['timestamp'] < start_time:
            return False
        if end_time and entry['timestamp'] > end_time:
            return False
            
        # Other filters
        if filters:
            for key, value in filters.items():
                if key in entry and entry[key] != value:
                    return False
                    
        return True
        
    def _setup_audit_logging(self):
        """Setup audit logging configuration"""
        
        # Configure structured logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
        )
        
        # Add correlation ID filter
        class CorrelationFilter(logging.Filter):
            def filter(self, record):
                record.correlation_id = correlation_id_var.get() or 'N/A'
                return True
                
        correlation_filter = CorrelationFilter()
        
        # Apply to all loggers
        for handler in logging.getLogger().handlers:
            handler.addFilter(correlation_filter)
            if not handler.formatter:
                handler.setFormatter(formatter)
