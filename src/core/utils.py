import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
import colorlog

class LoggingManager:
    """
    Centralized logging management for EdgeWatch.
    Provides structured logging with rotation, colors, and multiple output targets.
    """
    
    _configured = False
    
    @classmethod
    def setup_logging(cls, log_level='INFO', log_file=None, enable_colors=True, 
                     max_bytes=100*1024*1024, backup_count=5):
        """
        Setup comprehensive logging configuration for EdgeWatch.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (None for console only)
            enable_colors: Enable colored console output
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup log files to keep
        """
        if cls._configured:
            return
        
        # Create logs directory if needed
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        if enable_colors:
            console_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count
            )
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # EdgeWatch specific loggers
        cls._setup_edgewatch_loggers()
        
        cls._configured = True
        
        # Log startup message
        logger = logging.getLogger('edgewatch.startup')
        logger.info(f"EdgeWatch logging initialized - Level: {log_level}, File: {log_file}")
    
    @classmethod
    def _setup_edgewatch_loggers(cls):
        """Setup EdgeWatch specific logger configurations"""
        
        # Core system logger
        core_logger = logging.getLogger('edgewatch.core')
        core_logger.setLevel(logging.INFO)
        
        # Metrics logger for performance data
        metrics_logger = logging.getLogger('edgewatch.metrics')
        metrics_logger.setLevel(logging.DEBUG)
        
        # Communication logger for network operations
        comm_logger = logging.getLogger('edgewatch.communication')
        comm_logger.setLevel(logging.INFO)
        
        # Configuration logger
        config_logger = logging.getLogger('edgewatch.config')
        config_logger.setLevel(logging.WARNING)
        
        # Performance logger for benchmarking
        perf_logger = logging.getLogger('edgewatch.performance')
        perf_logger.setLevel(logging.INFO)


class SystemUtils:
    """
    System utility functions for EdgeWatch operations.
    """
    
    @staticmethod
    def get_system_info():
        """Get comprehensive system information"""
        import platform
        import psutil
        
        return {
            'platform': platform.platform(),
            'architecture': platform.architecture()[0],
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_total': psutil.disk_usage('/').total,
            'hostname': platform.node(),
            'system': platform.system(),
            'release': platform.release()
        }
    
    @staticmethod
    def format_bytes(bytes_value):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    @staticmethod
    def format_duration(seconds):
        """Format duration in seconds to human readable format"""
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.2f} minutes"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.2f} hours"
        else:
            days = seconds / 86400
            return f"{days:.2f} days"
    
    @staticmethod
    def ensure_directory(path):
        """Ensure directory exists, create if necessary"""
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_timestamp():
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat() + 'Z'
    
    @staticmethod
    def safe_float(value, default=0.0):
        """Safely convert value to float"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value, default=0):
        """Safely convert value to integer"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


class NetworkUtils:
    """
    Network utility functions for EdgeWatch communication.
    """
    
    @staticmethod
    def get_local_ip():
        """Get local IP address"""
        import socket
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def is_port_available(port, host='localhost'):
        """Check if a port is available"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((host, port))
            s.close()
            return result != 0
        except Exception:
            return False
    
    @staticmethod
    def get_network_interfaces():
        """Get available network interfaces"""
        try:
            import netifaces
            interfaces = []
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        interfaces.append({
                            'interface': interface,
                            'ip': addr['addr'],
                            'netmask': addr.get('netmask', ''),
                            'broadcast': addr.get('broadcast', '')
                        })
            return interfaces
        except ImportError:
            # Fallback if netifaces not available
            return [{'interface': 'default', 'ip': NetworkUtils.get_local_ip(), 
                    'netmask': '', 'broadcast': ''}]


class DataUtils:
    """
    Data manipulation and validation utilities.
    """
    
    @staticmethod
    def validate_json_schema(data, schema):
        """Validate data against JSON schema"""
        try:
            import jsonschema
            jsonschema.validate(data, schema)
            return True, None
        except ImportError:
            return True, "jsonschema not available"
        except jsonschema.ValidationError as e:
            return False, str(e)
    
    @staticmethod
    def deep_merge_dict(dict1, dict2):
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DataUtils.deep_merge_dict(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def sanitize_string(text, max_length=255):
        """Sanitize string for safe storage and transmission"""
        if not isinstance(text, str):
            text = str(text)
        
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length-3] + '...'
        
        return text
    
    @staticmethod
    def calculate_hash(data):
        """Calculate SHA256 hash of data"""
        import hashlib
        import json
        
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()


# Global logger getter
def get_logger(name):
    """Get a logger instance for the given name"""
    return logging.getLogger(f"edgewatch.{name}")


# Initialize default logging if not already configured
def init_default_logging():
    """Initialize default logging configuration"""
    if not LoggingManager._configured:
        LoggingManager.setup_logging(
            log_level='INFO',
            log_file='logs/edgewatch.log',
            enable_colors=True
        )
