"""
EdgeWatch Error Handler
Comprehensive error handling and recovery mechanisms for the EdgeWatch system.
Provides structured error classification, recovery strategies, and resilience mechanisms.
"""

import logging
import traceback
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from threading import Lock
import time
import json


class ErrorSeverity(Enum):
    """Error severity levels for classification"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(Enum):
    """Error categories for better classification"""
    NETWORK = "network"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RESOURCE = "resource"
    PROTOCOL = "protocol"
    INTERNAL = "internal"
    EXTERNAL = "external"


@dataclass
class ErrorContext:
    """Context information for errors"""
    timestamp: float
    node_id: str
    component: str
    function: str
    severity: ErrorSeverity
    category: ErrorCategory
    error_code: str
    message: str
    details: Dict[str, Any]
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3


class RecoveryStrategy:
    """Base class for recovery strategies"""
    
    def __init__(self, name: str, max_attempts: int = 3, backoff_factor: float = 1.5):
        self.name = name
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        
    def can_recover(self, error_context: ErrorContext) -> bool:
        """Check if this strategy can handle the error"""
        return error_context.recovery_attempts < self.max_attempts
        
    def recover(self, error_context: ErrorContext, **kwargs) -> bool:
        """Attempt recovery - returns True if successful"""
        raise NotImplementedError("Subclasses must implement recover method")
        
    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate backoff delay for retry attempts"""
        return min(60.0, (self.backoff_factor ** attempt))


class NetworkRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy for network-related errors"""
    
    def __init__(self):
        super().__init__("NetworkRecovery", max_attempts=5, backoff_factor=2.0)
        
    def can_recover(self, error_context: ErrorContext) -> bool:
        return (super().can_recover(error_context) and 
                error_context.category == ErrorCategory.NETWORK)
                
    def recover(self, error_context: ErrorContext, **kwargs) -> bool:
        """Attempt network recovery"""
        try:
            # Implement network-specific recovery logic
            connection_test = kwargs.get('connection_test')
            if connection_test and callable(connection_test):
                return connection_test()
            return True
        except Exception:
            return False


class DatabaseRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy for database-related errors"""
    
    def __init__(self):
        super().__init__("DatabaseRecovery", max_attempts=3, backoff_factor=1.5)
        
    def can_recover(self, error_context: ErrorContext) -> bool:
        return (super().can_recover(error_context) and 
                error_context.category == ErrorCategory.DATABASE)
                
    def recover(self, error_context: ErrorContext, **kwargs) -> bool:
        """Attempt database recovery"""
        try:
            # Implement database-specific recovery logic
            db_reconnect = kwargs.get('db_reconnect')
            if db_reconnect and callable(db_reconnect):
                return db_reconnect()
            return True
        except Exception:
            return False


class ResourceRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy for resource-related errors"""
    
    def __init__(self):
        super().__init__("ResourceRecovery", max_attempts=2, backoff_factor=1.0)
        
    def can_recover(self, error_context: ErrorContext) -> bool:
        return (super().can_recover(error_context) and 
                error_context.category == ErrorCategory.RESOURCE)
                
    def recover(self, error_context: ErrorContext, **kwargs) -> bool:
        """Attempt resource recovery"""
        try:
            # Implement resource cleanup and recovery
            cleanup_func = kwargs.get('cleanup_function')
            if cleanup_func and callable(cleanup_func):
                cleanup_func()
            return True
        except Exception:
            return False


class EdgeWatchErrorHandler:
    """
    Centralized error handling and recovery system for EdgeWatch.
    Provides comprehensive error management, recovery strategies, and monitoring.
    """
    
    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"EdgeWatch.ErrorHandler.{node_id}")
        
        # Error tracking
        self._error_history: List[ErrorContext] = []
        self._error_stats: Dict[str, int] = {}
        self._recovery_strategies: List[RecoveryStrategy] = []
        self._lock = Lock()
        
        # Configuration
        self.max_error_history = self.config.get('max_error_history', 1000)
        self.enable_auto_recovery = self.config.get('enable_auto_recovery', True)
        self.circuit_breaker_threshold = self.config.get('circuit_breaker_threshold', 10)
        
        # Initialize recovery strategies
        self._init_recovery_strategies()
        
        # Circuit breaker state
        self._circuit_breaker_state = {}
        
    def _init_recovery_strategies(self):
        """Initialize built-in recovery strategies"""
        self._recovery_strategies = [
            NetworkRecoveryStrategy(),
            DatabaseRecoveryStrategy(),
            ResourceRecoveryStrategy()
        ]
        
    def handle_error(self, error: Exception, component: str, function: str,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    category: ErrorCategory = ErrorCategory.INTERNAL,
                    error_code: Optional[str] = None,
                    additional_context: Optional[Dict[str, Any]] = None,
                    recovery_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle an error with context and attempt recovery if possible.
        Returns True if error was handled/recovered, False otherwise.
        """
        # Create error context
        error_context = ErrorContext(
            timestamp=time.time(),
            node_id=self.node_id,
            component=component,
            function=function,
            severity=severity,
            category=category,
            error_code=error_code or f"{category.value}_{int(time.time())}",
            message=str(error),
            details=additional_context or {},
            stack_trace=traceback.format_exc() if self.config.get('include_stack_trace', True) else None
        )
        
        # Log the error
        self._log_error(error_context)
        
        # Track error statistics
        self._track_error(error_context)
        
        # Check circuit breaker
        if self._is_circuit_breaker_open(component):
            self.logger.warning(f"Circuit breaker open for {component}, skipping recovery")
            return False
        
        # Attempt recovery if enabled
        recovery_successful = False
        if self.enable_auto_recovery:
            recovery_successful = self._attempt_recovery(error_context, recovery_context or {})
            
        # Store in history
        with self._lock:
            self._error_history.append(error_context)
            if len(self._error_history) > self.max_error_history:
                self._error_history.pop(0)
                
        return recovery_successful
        
    def _log_error(self, error_context: ErrorContext):
        """Log error with appropriate level"""
        log_message = (f"[{error_context.severity.value.upper()}] "
                      f"{error_context.component}.{error_context.function}: "
                      f"{error_context.message}")
        
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        elif error_context.severity == ErrorSeverity.LOW:
            self.logger.info(log_message)
        else:
            self.logger.debug(log_message)
            
    def _track_error(self, error_context: ErrorContext):
        """Track error statistics"""
        with self._lock:
            key = f"{error_context.component}_{error_context.category.value}"
            self._error_stats[key] = self._error_stats.get(key, 0) + 1
            
            # Update circuit breaker state
            if self._error_stats[key] >= self.circuit_breaker_threshold:
                self._circuit_breaker_state[error_context.component] = time.time()
                
    def _is_circuit_breaker_open(self, component: str) -> bool:
        """Check if circuit breaker is open for a component"""
        if component not in self._circuit_breaker_state:
            return False
            
        # Circuit breaker timeout (5 minutes)
        timeout = self.config.get('circuit_breaker_timeout', 300)
        return (time.time() - self._circuit_breaker_state[component]) < timeout
        
    def _attempt_recovery(self, error_context: ErrorContext, recovery_context: Dict[str, Any]) -> bool:
        """Attempt to recover from error using available strategies"""
        for strategy in self._recovery_strategies:
            if strategy.can_recover(error_context):
                try:
                    self.logger.info(f"Attempting recovery with {strategy.name}")
                    
                    # Add backoff delay
                    if error_context.recovery_attempts > 0:
                        delay = strategy.get_backoff_delay(error_context.recovery_attempts)
                        self.logger.info(f"Waiting {delay:.1f}s before recovery attempt")
                        time.sleep(delay)
                    
                    # Attempt recovery
                    error_context.recovery_attempts += 1
                    if strategy.recover(error_context, **recovery_context):
                        self.logger.info(f"Recovery successful with {strategy.name}")
                        return True
                        
                except Exception as recovery_error:
                    self.logger.error(f"Recovery failed with {strategy.name}: {recovery_error}")
                    
        return False
        
    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """Add a custom recovery strategy"""
        self._recovery_strategies.append(strategy)
        
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        with self._lock:
            return {
                'total_errors': len(self._error_history),
                'error_counts': self._error_stats.copy(),
                'circuit_breaker_state': self._circuit_breaker_state.copy(),
                'recent_errors': len([e for e in self._error_history 
                                    if time.time() - e.timestamp < 3600])  # Last hour
            }
            
    def get_error_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error history"""
        with self._lock:
            recent_errors = self._error_history[-limit:] if limit > 0 else self._error_history
            return [self._error_context_to_dict(error) for error in recent_errors]
            
    def _error_context_to_dict(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Convert error context to dictionary"""
        return {
            'timestamp': error_context.timestamp,
            'node_id': error_context.node_id,
            'component': error_context.component,
            'function': error_context.function,
            'severity': error_context.severity.value,
            'category': error_context.category.value,
            'error_code': error_context.error_code,
            'message': error_context.message,
            'details': error_context.details,
            'recovery_attempts': error_context.recovery_attempts,
            'max_recovery_attempts': error_context.max_recovery_attempts
        }
        
    def clear_error_history(self):
        """Clear error history"""
        with self._lock:
            self._error_history.clear()
            self._error_stats.clear()
            
    def reset_circuit_breaker(self, component: str):
        """Reset circuit breaker for a component"""
        with self._lock:
            if component in self._circuit_breaker_state:
                del self._circuit_breaker_state[component]
            # Reset error count for component
            keys_to_reset = [key for key in self._error_stats.keys() if key.startswith(f"{component}_")]
            for key in keys_to_reset:
                self._error_stats[key] = 0


def create_error_handler(node_id: str, config: Optional[Dict[str, Any]] = None) -> EdgeWatchErrorHandler:
    """Factory function to create error handler"""
    return EdgeWatchErrorHandler(node_id, config)


# Decorator for automatic error handling
def handle_errors(component: str, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 category: ErrorCategory = ErrorCategory.INTERNAL,
                 recovery_context: Optional[Dict[str, Any]] = None):
    """Decorator for automatic error handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Try to get error handler from first argument (usually self)
                error_handler = None
                if args and hasattr(args[0], 'error_handler'):
                    error_handler = args[0].error_handler
                
                if error_handler:
                    error_handler.handle_error(
                        error=e,
                        component=component,
                        function=func.__name__,
                        severity=severity,
                        category=category,
                        recovery_context=recovery_context
                    )
                else:
                    # Fallback logging
                    logging.getLogger("EdgeWatch.ErrorHandler").error(
                        f"Error in {component}.{func.__name__}: {e}"
                    )
                raise
        return wrapper
    return decorator
