#!/usr/bin/env python3
"""
EdgeWatch Main Application Entry Point

This is the main entry point for the EdgeWatch distributed monitoring system.
It initializes and starts all core components including the REST API server,
gossip protocol handler, and monitoring services.
"""

import sys
import os
import signal
import asyncio
import logging
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, jsonify, request
from werkzeug.serving import run_simple
from src.core.edgewatch_daemon import EdgeWatchDaemon
from src.api.routes import create_api_routes
from src.monitoring.health_monitor import HealthMonitor
from src.communication.gossip_protocol import GossipProtocol
import configparser

# Global application state
app = None
daemon = None
health_monitor = None
gossip_protocol = None

def create_app(config_path='config/default.ini'):
    """Create and configure the Flask application"""
    global app, daemon, health_monitor, gossip_protocol
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'edgewatch-dev-key-2025')
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Initialize core components
    daemon = EdgeWatchDaemon(config)
    health_monitor = HealthMonitor(config)
    gossip_protocol = GossipProtocol(config)
    
    # Register API routes
    create_api_routes(app, daemon, health_monitor, gossip_protocol)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers and monitoring"""
        try:
            status = health_monitor.get_system_health()
            return jsonify({
                'status': 'healthy' if status['overall_health'] > 0.8 else 'degraded',
                'timestamp': status['timestamp'],
                'version': '1.0.0',
                'node_id': daemon.node_id,
                'uptime': daemon.get_uptime(),
                'details': status
            })
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500
    
    # Root endpoint
    @app.route('/')
    def root():
        """Root endpoint with basic information"""
        return jsonify({
            'name': 'EdgeWatch',
            'description': 'Distributed Edge Computing Monitoring Platform',
            'version': '1.0.0',
            'node_id': daemon.node_id,
            'endpoints': {
                'health': '/health',
                'api': '/api',
                'dashboard': '/dashboard',
                'metrics': '/metrics'
            }
        })
    
    return app

def setup_logging():
    """Configure logging for the application"""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/edgewatch.log')
        ]
    )

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    if daemon:
        daemon.stop()
    if health_monitor:
        health_monitor.stop()
    if gossip_protocol:
        gossip_protocol.stop()
    
    logging.info("EdgeWatch shutdown complete")
    sys.exit(0)

def main():
    """Main application entry point"""
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Create logs directory if it doesn't exist
    Path('logs').mkdir(exist_ok=True)
    
    logger.info("Starting EdgeWatch Distributed Monitoring System...")
    
    # Determine configuration file
    config_file = os.environ.get('EDGEWATCH_CONFIG', 'config/production.ini')
    if not os.path.exists(config_file):
        config_file = 'config/default.ini'
    
    logger.info(f"Using configuration file: {config_file}")
    
    try:
        # Create Flask application
        app = create_app(config_file)
        
        # Start background services
        logger.info("Starting core services...")
        daemon.start()
        health_monitor.start()
        gossip_protocol.start()
        
        # Get configuration
        host = os.environ.get('EDGEWATCH_HOST', '0.0.0.0')
        port = int(os.environ.get('EDGEWATCH_PORT', '5000'))
        debug = os.environ.get('EDGEWATCH_DEBUG', 'false').lower() == 'true'
        
        logger.info(f"Starting EdgeWatch server on {host}:{port}")
        logger.info(f"Node ID: {daemon.node_id}")
        logger.info(f"Cluster mode: {'enabled' if daemon.cluster_mode else 'disabled'}")
        
        # Start the web server
        if debug:
            app.run(host=host, port=port, debug=True)
        else:
            run_simple(host, port, app, threaded=True, use_reloader=False)
            
    except Exception as e:
        logger.error(f"Failed to start EdgeWatch: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
