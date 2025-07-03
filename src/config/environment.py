"""
EdgeWatch Environment Configuration Manager
Manages environment-specific configurations and settings validation.
"""

import os
import configparser
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class Environment(Enum):
    """Supported deployment environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    STAGING = "staging"


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False


@dataclass
class RedisConfig:
    """Redis configuration settings"""
    url: str
    pool_size: int = 10
    socket_timeout: int = 5
    connection_timeout: int = 5


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    secret_key: str
    api_key_required: bool = True
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window: int = 3600
    cors_enabled: bool = True
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    metrics_enabled: bool = True
    health_check_interval: int = 30
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "cpu": 80.0,
        "memory": 85.0,
        "disk": 90.0,
        "network_latency": 1000.0
    })
    prometheus_enabled: bool = True
    grafana_enabled: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    file_path: Optional[str] = None
    max_size: str = "100MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_enabled: bool = True


@dataclass
class GossipConfig:
    """Gossip protocol configuration"""
    enabled: bool = True
    interval: int = 30
    fanout: int = 3
    max_peers: int = 50
    timeout: int = 10


@dataclass
class PerformanceConfig:
    """Performance and resource configuration"""
    worker_threads: int = 4
    connection_pool_size: int = 50
    request_timeout: int = 30
    max_content_length: str = "16MB"
    enable_compression: bool = True


class EnvironmentConfigManager:
    """
    Manages environment-specific configurations for EdgeWatch.
    Handles loading, validation, and access to configuration settings.
    """
    
    def __init__(self, environment: Optional[Union[str, Environment]] = None):
        self.environment = self._determine_environment(environment)
        self.config_dir = Path(__file__).parent
        self.config_file = self.config_dir / f"{self.environment.value}.ini"
        
        # Configuration objects
        self.database: Optional[DatabaseConfig] = None
        self.redis: Optional[RedisConfig] = None
        self.security: Optional[SecurityConfig] = None
        self.monitoring: Optional[MonitoringConfig] = None
        self.logging: Optional[LoggingConfig] = None
        self.gossip: Optional[GossipConfig] = None
        self.performance: Optional[PerformanceConfig] = None
        
        # Core settings
        self.node_id: str = ""
        self.cluster_mode: bool = False
        self.debug: bool = False
        self.bind_host: str = "localhost"
        self.bind_port: int = 5000
        self.dashboard_port: int = 8080
        self.metrics_port: int = 9090
        
        # Load configuration
        self._load_configuration()
        
        # Setup logging
        self._setup_logging()
        
        self.logger = logging.getLogger(f"EdgeWatch.ConfigManager.{self.node_id}")
        self.logger.info(f"Configuration loaded for environment: {self.environment.value}")
    
    def _determine_environment(self, environment: Optional[Union[str, Environment]]) -> Environment:
        """Determine the current environment"""
        if environment:
            if isinstance(environment, str):
                return Environment(environment.lower())
            return environment
        
        # Check environment variable
        env_var = os.getenv("EDGEWATCH_ENV", "development").lower()
        try:
            return Environment(env_var)
        except ValueError:
            return Environment.DEVELOPMENT
    
    def _load_configuration(self):
        """Load configuration from file"""
        if not self.config_file.exists():
            # Fall back to default configuration
            self.config_file = self.config_dir / "default.ini"
            
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        config = configparser.ConfigParser()
        config.read(self.config_file)
        
        # Load core settings
        self._load_core_settings(config)
        
        # Load component configurations
        self.database = self._load_database_config(config)
        self.redis = self._load_redis_config(config)
        self.security = self._load_security_config(config)
        self.monitoring = self._load_monitoring_config(config)
        self.logging = self._load_logging_config(config)
        self.gossip = self._load_gossip_config(config)
        self.performance = self._load_performance_config(config)
    
    def _load_core_settings(self, config: configparser.ConfigParser):
        """Load core application settings"""
        default_section = config['DEFAULT']
        
        self.node_id = default_section.get('node_id', 'edgewatch-node-001')
        self.cluster_mode = default_section.getboolean('cluster_mode', False)
        self.debug = default_section.getboolean('debug', False)
        self.bind_host = default_section.get('bind_host', 'localhost')
        self.bind_port = default_section.getint('bind_port', 5000)
        self.dashboard_port = default_section.getint('dashboard_port', 8080)
        self.metrics_port = default_section.getint('metrics_port', 9090)
    
    def _load_database_config(self, config: configparser.ConfigParser) -> DatabaseConfig:
        """Load database configuration"""
        default_section = config['DEFAULT']
        
        return DatabaseConfig(
            url=default_section.get('database_url', 'sqlite:///edgewatch.db'),
            pool_size=default_section.getint('database_pool_size', 10),
            max_overflow=default_section.getint('database_max_overflow', 20),
            pool_timeout=default_section.getint('database_pool_timeout', 30),
            echo=self.debug
        )
    
    def _load_redis_config(self, config: configparser.ConfigParser) -> RedisConfig:
        """Load Redis configuration"""
        default_section = config['DEFAULT']
        
        return RedisConfig(
            url=default_section.get('redis_url', 'redis://localhost:6379/0'),
            pool_size=default_section.getint('redis_pool_size', 10),
            socket_timeout=default_section.getint('redis_socket_timeout', 5),
            connection_timeout=default_section.getint('redis_connection_timeout', 5)
        )
    
    def _load_security_config(self, config: configparser.ConfigParser) -> SecurityConfig:
        """Load security configuration"""
        default_section = config['DEFAULT']
        
        return SecurityConfig(
            secret_key=default_section.get('secret_key', 'default-secret-key'),
            api_key_required=default_section.getboolean('api_key_required', True),
            rate_limit_enabled=default_section.getboolean('rate_limit_enabled', True),
            rate_limit_requests=default_section.getint('rate_limit_requests', 1000),
            rate_limit_window=default_section.getint('rate_limit_window', 3600),
            cors_enabled=default_section.getboolean('cors_enabled', True),
            cors_origins=default_section.get('cors_origins', '*').split(',')
        )
    
    def _load_monitoring_config(self, config: configparser.ConfigParser) -> MonitoringConfig:
        """Load monitoring configuration"""
        default_section = config['DEFAULT']
        
        alert_thresholds = {
            'cpu': default_section.getfloat('alert_thresholds_cpu', 80.0),
            'memory': default_section.getfloat('alert_thresholds_memory', 85.0),
            'disk': default_section.getfloat('alert_thresholds_disk', 90.0),
            'network_latency': default_section.getfloat('alert_thresholds_network_latency', 1000.0)
        }
        
        return MonitoringConfig(
            metrics_enabled=default_section.getboolean('metrics_enabled', True),
            health_check_interval=default_section.getint('health_check_interval', 30),
            alert_thresholds=alert_thresholds,
            prometheus_enabled=default_section.getboolean('prometheus_enabled', True),
            grafana_enabled=default_section.getboolean('grafana_enabled', True)
        )
    
    def _load_logging_config(self, config: configparser.ConfigParser) -> LoggingConfig:
        """Load logging configuration"""
        default_section = config['DEFAULT']
        
        return LoggingConfig(
            level=default_section.get('log_level', 'INFO'),
            file_path=default_section.get('log_file', None),
            max_size=default_section.get('log_max_size', '100MB'),
            backup_count=default_section.getint('log_backup_count', 5),
            format=default_section.get('log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            console_enabled=default_section.getboolean('log_console_enabled', True)
        )
    
    def _load_gossip_config(self, config: configparser.ConfigParser) -> GossipConfig:
        """Load gossip protocol configuration"""
        default_section = config['DEFAULT']
        
        return GossipConfig(
            enabled=default_section.getboolean('gossip_enabled', True),
            interval=default_section.getint('gossip_interval', 30),
            fanout=default_section.getint('gossip_fanout', 3),
            max_peers=default_section.getint('gossip_max_peers', 50),
            timeout=default_section.getint('gossip_timeout', 10)
        )
    
    def _load_performance_config(self, config: configparser.ConfigParser) -> PerformanceConfig:
        """Load performance configuration"""
        default_section = config['DEFAULT']
        
        return PerformanceConfig(
            worker_threads=default_section.getint('worker_threads', 4),
            connection_pool_size=default_section.getint('connection_pool_size', 50),
            request_timeout=default_section.getint('request_timeout', 30),
            max_content_length=default_section.get('max_content_length', '16MB'),
            enable_compression=default_section.getboolean('enable_compression', True)
        )
    
    def _setup_logging(self):
        """Setup logging configuration"""
        if not self.logging:
            return
        
        # Create logs directory if it doesn't exist
        if self.logging.file_path:
            log_dir = Path(self.logging.file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.logging.level.upper()),
            format=self.logging.format,
            handlers=[]
        )
        
        # Add console handler
        if self.logging.console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(self.logging.format))
            logging.getLogger().addHandler(console_handler)
        
        # Add file handler
        if self.logging.file_path:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                self.logging.file_path,
                maxBytes=self._parse_size(self.logging.max_size),
                backupCount=self.logging.backup_count
            )
            file_handler.setFormatter(logging.Formatter(self.logging.format))
            logging.getLogger().addHandler(file_handler)
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return {
            'environment': self.environment.value,
            'node_id': self.node_id,
            'cluster_mode': self.cluster_mode,
            'debug': self.debug,
            'bind_host': self.bind_host,
            'bind_port': self.bind_port,
            'dashboard_port': self.dashboard_port,
            'metrics_port': self.metrics_port,
            'database': self.database.__dict__ if self.database else {},
            'redis': self.redis.__dict__ if self.redis else {},
            'security': self.security.__dict__ if self.security else {},
            'monitoring': self.monitoring.__dict__ if self.monitoring else {},
            'logging': self.logging.__dict__ if self.logging else {},
            'gossip': self.gossip.__dict__ if self.gossip else {},
            'performance': self.performance.__dict__ if self.performance else {}
        }
    
    def validate_configuration(self) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Validate ports
        if not (1024 <= self.bind_port <= 65535):
            errors.append(f"Invalid bind_port: {self.bind_port}")
        
        if not (1024 <= self.dashboard_port <= 65535):
            errors.append(f"Invalid dashboard_port: {self.dashboard_port}")
        
        if not (1024 <= self.metrics_port <= 65535):
            errors.append(f"Invalid metrics_port: {self.metrics_port}")
        
        # Validate database URL
        if not self.database or not self.database.url:
            errors.append("Database URL is required")
        
        # Validate security settings
        if self.security and self.environment == Environment.PRODUCTION:
            if self.security.secret_key == "default-secret-key":
                errors.append("Default secret key not allowed in production")
        
        if errors:
            for error in errors:
                logging.error(f"Configuration validation error: {error}")
            return False
        
        return True
    
    def reload_configuration(self):
        """Reload configuration from file"""
        self._load_configuration()
        self.logger.info("Configuration reloaded")


# Global configuration manager instance
_config_manager: Optional[EnvironmentConfigManager] = None


def get_config_manager(environment: Optional[Union[str, Environment]] = None) -> EnvironmentConfigManager:
    """Get or create configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = EnvironmentConfigManager(environment)
    return _config_manager


def reload_config():
    """Reload configuration"""
    global _config_manager
    if _config_manager:
        _config_manager.reload_configuration()
