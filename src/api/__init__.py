"""
EdgeWatch API Module

This module provides the REST API interface for the EdgeWatch monitoring system.
"""

from .routes import create_api_routes

__all__ = ['create_api_routes']
