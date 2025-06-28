import configparser
import os
import logging
from threading import Lock

logger = logging.getLogger("edgewatch.config")

class ConfigManager:
    """
    Thread-safe singleton configuration manager for EdgeWatch.
    Handles loading, parsing, and accessing configuration values.
    """
    
    _instance = None
    _lock = Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._config = configparser.ConfigParser()
        self._config_file = None
        self._default_config = self._get_default_config()
        self._initialized = True
        
        # Load default configuration
        self._load_defaults()
    
    @classmethod
    def instance(cls):
        """Returns the singleton instance of ConfigManager"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _get_default_config(self):
        """Define default configuration values"""
        return {
            'EdgeWatch': {
                'version': '1.0.0',
                'project_name': 'EdgeWatch',
                'description': 'Decentralized Edge Monitoring System'
            },
            'Network': {
                'default_port': '8080',
                'gossip_port': '8081', 
                'discovery_port': '8082',
                'heartbeat_interval': '5',
                'connection_timeout': '10'
            },
            'Monitoring': {
                'collection_interval': '1',
                'data_retention_days': '30',
                'max_buffer_size': '1000',
                'enable_metrics': 'true'
            },
            'Storage': {
                'database_type': 'sqlite',
                'database_path': 'data/edgewatch.db',
                'backup_enabled': 'true',
                'backup_interval': '3600'
            },
            'Logging': {
                'log_level': 'INFO',
                'log_file': 'logs/edgewatch.log',
                'log_rotation': 'daily',
                'max_log_size': '100MB'
            }
        }
    
    def _load_defaults(self):
        """Load default configuration values"""
        for section_name, section_data in self._default_config.items():
            self._config.add_section(section_name)
            for key, value in section_data.items():
                self._config.set(section_name, key, value)
    
    def load_config(self, config_file):
        """Load configuration from file"""
        try:
            if os.path.exists(config_file):
                self._config.read(config_file)
                self._config_file = config_file
                logger.info(f"Configuration loaded from {config_file}")
            else:
                logger.warning(f"Configuration file {config_file} not found, using defaults")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_file}: {e}")
            raise
    
    def get(self, section, key, fallback=None):
        """Get configuration value"""
        try:
            return self._config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise
    
    def get_int(self, section, key, fallback=None):
        """Get configuration value as integer"""
        try:
            return self._config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            if fallback is not None:
                return fallback
            raise
    
    def get_float(self, section, key, fallback=None):
        """Get configuration value as float"""
        try:
            return self._config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            if fallback is not None:
                return fallback
            raise
    
    def get_boolean(self, section, key, fallback=None):
        """Get configuration value as boolean"""
        try:
            return self._config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            if fallback is not None:
                return fallback
            raise
    
    def set(self, section, key, value):
        """Set configuration value"""
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))
    
    def save_config(self, config_file=None):
        """Save current configuration to file"""
        file_to_save = config_file or self._config_file
        if file_to_save:
            try:
                os.makedirs(os.path.dirname(file_to_save), exist_ok=True)
                with open(file_to_save, 'w') as f:
                    self._config.write(f)
                logger.info(f"Configuration saved to {file_to_save}")
            except Exception as e:
                logger.error(f"Error saving configuration to {file_to_save}: {e}")
                raise
        else:
            logger.warning("No configuration file specified for saving")
    
    def get_section(self, section_name):
        """Get all values from a configuration section as dictionary"""
        try:
            return dict(self._config.items(section_name))
        except configparser.NoSectionError:
            return {}
    
    def has_section(self, section_name):
        """Check if configuration section exists"""
        return self._config.has_section(section_name)
    
    def has_option(self, section, key):
        """Check if configuration option exists"""
        return self._config.has_option(section, key)
    
    def get_sections(self):
        """Get all configuration section names"""
        return self._config.sections()
    
    def reload_config(self):
        """Reload configuration from file"""
        if self._config_file:
            self.load_config(self._config_file)
        else:
            logger.warning("No configuration file to reload")


class Singleton:
    """
    A thread-safe helper class to ease implementing singletons.
    This should be used as a decorator -- not a metaclass -- to the
    class that should be a singleton.

    The decorated class can define one `__init__` function that
    takes only the `self` argument. Also, the decorated class cannot be
    inherited from. Other than that, there are no restrictions that apply
    to the decorated class.

    To get the singleton instance, use the `instance` method. Trying
    to use `__call__` will result in a `TypeError` being raised.
    """

    def __init__(self, decorated):
        self._decorated = decorated
        self._instance = None
        self._lock = Lock()

    def instance(self):
        """
        Returns the singleton instance. Upon its first call, it creates a
        new instance of the decorated class and calls its `__init__` method.
        On all subsequent calls, the already created instance is returned.
        """
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._decorated()
        return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)
