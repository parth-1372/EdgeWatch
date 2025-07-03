#!/bin/bash

# EdgeWatch Development Setup Script
# Quick development environment setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[DEV] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Setup development environment
setup_dev() {
    log "Setting up development environment..."
    
    cd "$PROJECT_ROOT"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        log "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    # Activate virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    fi
    
    # Install dependencies
    log "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Setup pre-commit hooks
    if command -v pre-commit &> /dev/null; then
        log "Installing pre-commit hooks..."
        pre-commit install
    fi
    
    success "Development environment setup completed"
}

# Start development containers
start_dev() {
    log "Starting development containers..."
    
    cd "$SCRIPT_DIR"
    
    # Start development services
    docker-compose -f docker-compose.dev.yml up -d
    
    success "Development containers started"
    echo ""
    echo "Development Services:"
    echo "  EdgeWatch API:    http://localhost:5000"
    echo "  Dashboard:        http://localhost:8080"
    echo "  Database:         localhost:5432"
    echo "  Redis:            localhost:6379"
    echo ""
}

# Stop development containers
stop_dev() {
    log "Stopping development containers..."
    
    cd "$SCRIPT_DIR"
    docker-compose -f docker-compose.dev.yml down
    
    success "Development containers stopped"
}

# Run tests
run_tests() {
    log "Running EdgeWatch tests..."
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    fi
    
    # Run tests
    python -m pytest tests/ -v
    
    success "Tests completed"
}

# Clean development environment
clean_dev() {
    log "Cleaning development environment..."
    
    cd "$SCRIPT_DIR"
    
    # Stop containers
    docker-compose -f docker-compose.dev.yml down -v
    
    # Remove development images
    docker rmi edgewatch:dev 2>/dev/null || true
    
    # Clean Python cache
    cd "$PROJECT_ROOT"
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    success "Development environment cleaned"
}

# Show logs
show_logs() {
    local service="${1:-edgewatch-dev}"
    
    cd "$SCRIPT_DIR"
    docker-compose -f docker-compose.dev.yml logs -f "$service"
}

# Main execution
case "${1:-help}" in
    "setup")
        setup_dev
        ;;
    "start")
        start_dev
        ;;
    "stop")
        stop_dev
        ;;
    "restart")
        stop_dev
        start_dev
        ;;
    "test")
        run_tests
        ;;
    "clean")
        clean_dev
        ;;
    "logs")
        show_logs "${2:-}"
        ;;
    "help"|*)
        echo "EdgeWatch Development Script"
        echo ""
        echo "Usage: $0 {setup|start|stop|restart|test|clean|logs}"
        echo ""
        echo "Commands:"
        echo "  setup    - Setup development environment"
        echo "  start    - Start development containers"
        echo "  stop     - Stop development containers"
        echo "  restart  - Restart development containers"
        echo "  test     - Run tests"
        echo "  clean    - Clean development environment"
        echo "  logs     - Show container logs"
        echo ""
        ;;
esac
