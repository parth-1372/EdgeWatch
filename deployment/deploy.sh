#!/bin/bash

# EdgeWatch Deployment Script
# Automated deployment for production environments

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-production}"
EDGEWATCH_VERSION="${EDGEWATCH_VERSION:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Print banner
print_banner() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                          EdgeWatch Deployment Script                        ║"
    echo "║                     Automated Container Deployment                          ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    local errors=0
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        errors=$((errors + 1))
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
        errors=$((errors + 1))
    fi
    
    # Check Docker daemon is running
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running. Please start Docker first."
        errors=$((errors + 1))
    fi
    
    # Check available disk space (minimum 2GB)
    available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 2097152 ]; then
        warning "Low disk space detected. At least 2GB recommended."
    fi
    
    if [ $errors -gt 0 ]; then
        error "Prerequisites check failed with $errors errors."
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Build EdgeWatch images
build_images() {
    log "Building EdgeWatch Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build main EdgeWatch image
    log "Building EdgeWatch application image..."
    docker build -t edgewatch:${EDGEWATCH_VERSION} -f deployment/Dockerfile .
    
    # Tag as latest if version is not specified
    if [ "$EDGEWATCH_VERSION" != "latest" ]; then
        docker tag edgewatch:${EDGEWATCH_VERSION} edgewatch:latest
    fi
    
    success "Docker images built successfully"
}

# Setup configuration
setup_configuration() {
    log "Setting up configuration files..."
    
    cd "$SCRIPT_DIR"
    
    # Create necessary directories
    mkdir -p ../data ../logs ../config
    mkdir -p ./monitoring/grafana/dashboards ./monitoring/grafana/provisioning
    mkdir -p ./nginx/ssl ./sql
    
    # Copy configuration files if they don't exist
    if [ ! -f "../config/production.ini" ]; then
        log "Creating production configuration..."
        cp "../config/default.ini" "../config/production.ini"
    fi
    
    # Generate SSL certificates if they don't exist
    if [ ! -f "./nginx/ssl/edgewatch.crt" ]; then
        log "Generating self-signed SSL certificates..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ./nginx/ssl/edgewatch.key \
            -out ./nginx/ssl/edgewatch.crt \
            -subj "/C=US/ST=State/L=City/O=EdgeWatch/CN=localhost"
    fi
    
    success "Configuration setup completed"
}

# Deploy using Docker Compose
deploy_compose() {
    log "Deploying EdgeWatch using Docker Compose..."
    
    cd "$SCRIPT_DIR"
    
    # Determine compose file
    local compose_file="docker-compose.yml"
    if [ "$DEPLOYMENT_ENV" = "development" ]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    # Pull latest images for external services
    log "Pulling external service images..."
    docker-compose -f "$compose_file" pull edgewatch-database edgewatch-monitoring edgewatch-grafana edgewatch-redis edgewatch-nginx
    
    # Deploy services
    log "Starting EdgeWatch services..."
    docker-compose -f "$compose_file" up -d
    
    success "EdgeWatch deployed successfully"
}

# Health check
health_check() {
    log "Performing health checks..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:5000/health &> /dev/null; then
            success "Primary node health check passed"
            break
        fi
        
        attempt=$((attempt + 1))
        log "Health check attempt $attempt/$max_attempts..."
        sleep 5
    done
    
    if [ $attempt -eq $max_attempts ]; then
        error "Health check failed after $max_attempts attempts"
        return 1
    fi
    
    # Check secondary node
    if curl -f http://localhost:5001/health &> /dev/null; then
        success "Secondary node health check passed"
    else
        warning "Secondary node health check failed"
    fi
    
    # Check database
    if docker-compose -f docker-compose.yml exec -T edgewatch-database pg_isready -U edgewatch &> /dev/null; then
        success "Database health check passed"
    else
        warning "Database health check failed"
    fi
    
    success "Health checks completed"
}

# Show deployment status
show_status() {
    log "Deployment Status:"
    echo ""
    
    cd "$SCRIPT_DIR"
    docker-compose -f docker-compose.yml ps
    
    echo ""
    echo -e "${GREEN}🎯 EdgeWatch Monitoring Access URLs:${NC}"
    echo "  📊 Main Dashboard:       http://localhost:8080 (real-time monitoring)"
    echo "  📈 Analytics (Grafana):  http://localhost:3000 (admin/edgewatch_admin_2025)"
    echo "  📋 Metrics (Prometheus): http://localhost:9000 (raw metrics & queries)"
    echo "  🔌 Primary API:          http://localhost:5000"
    echo "  🔌 Secondary API:        http://localhost:5001"
    echo "  🌐 Load Balancer:        http://localhost"
    echo ""
    echo -e "${BLUE}📖 For detailed monitoring guide, see: docs/user/monitoring-access.md${NC}"
    echo -e "${BLUE}📋 Quick reference: MONITORING-QUICK-REF.md${NC}"
    echo ""
}

# Cleanup function
cleanup() {
    log "Cleaning up deployment resources..."
    
    cd "$SCRIPT_DIR"
    
    # Stop services
    docker-compose -f docker-compose.yml down
    
    # Remove images if requested
    if [ "$1" = "--remove-images" ]; then
        log "Removing EdgeWatch images..."
        docker rmi edgewatch:latest edgewatch:${EDGEWATCH_VERSION} 2>/dev/null || true
    fi
    
    # Remove volumes if requested
    if [ "$1" = "--remove-volumes" ]; then
        log "Removing volumes..."
        docker-compose -f docker-compose.yml down -v
    fi
    
    success "Cleanup completed"
}

# Update deployment
update_deployment() {
    log "Updating EdgeWatch deployment..."
    
    # Pull latest code (if in git repository)
    if [ -d "$PROJECT_ROOT/.git" ]; then
        log "Pulling latest code..."
        cd "$PROJECT_ROOT"
        git pull origin main
    fi
    
    # Rebuild images
    build_images
    
    # Restart services
    cd "$SCRIPT_DIR"
    docker-compose -f docker-compose.yml up -d --force-recreate
    
    success "Deployment updated successfully"
}

# Backup data
backup_data() {
    log "Creating backup of EdgeWatch data..."
    
    local backup_dir="./backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    cd "$SCRIPT_DIR"
    
    # Backup database
    docker-compose -f docker-compose.yml exec -T edgewatch-database pg_dump -U edgewatch edgewatch > "$backup_dir/database.sql"
    
    # Backup volumes
    docker run --rm -v edgewatch_data:/source -v "$(pwd)/$backup_dir":/backup alpine tar czf /backup/edgewatch_data.tar.gz -C /source .
    docker run --rm -v edgewatch_logs:/source -v "$(pwd)/$backup_dir":/backup alpine tar czf /backup/edgewatch_logs.tar.gz -C /source .
    
    success "Backup created at $backup_dir"
}

# Main execution
main() {
    print_banner
    
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            setup_configuration
            build_images
            deploy_compose
            health_check
            show_status
            ;;
        "update")
            update_deployment
            health_check
            show_status
            ;;
        "status")
            show_status
            ;;
        "cleanup")
            cleanup "${2:-}"
            ;;
        "backup")
            backup_data
            ;;
        "health")
            health_check
            ;;
        *)
            echo "Usage: $0 {deploy|update|status|cleanup|backup|health}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Full deployment (default)"
            echo "  update   - Update existing deployment"
            echo "  status   - Show deployment status"
            echo "  cleanup  - Stop and cleanup resources"
            echo "  backup   - Create data backup"
            echo "  health   - Run health checks"
            echo ""
            echo "Cleanup options:"
            echo "  --remove-images   - Also remove Docker images"
            echo "  --remove-volumes  - Also remove data volumes"
            echo ""
            echo "Environment variables:"
            echo "  DEPLOYMENT_ENV     - production|development (default: production)"
            echo "  EDGEWATCH_VERSION  - Image version tag (default: latest)"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
