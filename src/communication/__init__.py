"""
EdgeWatch Communication Module

This module provides communication protocols and utilities for EdgeWatch nodes.
"""

from .gossip_protocol import GossipProtocol, MessageFilter, AdaptiveScheduler, create_communication_protocol

__all__ = [
    'GossipProtocol',
    'MessageFilter', 
    'AdaptiveScheduler',
    'create_communication_protocol'
]
