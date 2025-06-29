"""
EdgeWatch Client Module

This module provides client interfaces for interacting with EdgeWatch nodes.
"""

from .query_interface import EdgeWatchQueryClient, QueryResponse, QueryResult, create_query_client

__all__ = [
    'EdgeWatchQueryClient',
    'QueryResponse', 
    'QueryResult',
    'create_query_client'
]
