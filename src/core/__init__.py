"""
EdgeWatch Core Module

This module contains the core components for the EdgeWatch distributed monitoring system.
It provides the fundamental building blocks for edge node management, configuration,
and inter-node communication in volatile edge computing environments.

Components:
- EdgeNode: Main monitoring node implementation
- ConfigManager: Thread-safe configuration management
"""

from .edge_node import EdgeNode
from .config_manager import ConfigManager, ConfigurationError

__all__ = ['EdgeNode', 'ConfigManager', 'ConfigurationError']
