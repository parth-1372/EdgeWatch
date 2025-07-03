#!/bin/bash

# EdgeWatch Production Optimization Script
# Optimizes container deployment for production environments

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Performance optimization settings
optimize_docker_settings() {
    log "Optimizing Docker settings for production..."
    
    # Create optimized Docker daemon configuration
    cat > /tmp/daemon.json << EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],
    "dns": ["8.8.8.8", "8.8.4.4"],
    "max-concurrent-downloads": 6,
    "max-concurrent-uploads": 5,
    "default-shm-size": "64M",
    "userland-proxy": false
}
EOF
    
    # Backup existing configuration
    if [ -f "/etc/docker/daemon.json" ]; then
        sudo cp "/etc/docker/daemon.json" "/etc/docker/daemon.json.backup"
    fi
    
    # Apply optimized configuration (requires sudo)
    if command -v sudo >/dev/null 2>&1; then
        warning "Docker optimization requires sudo access. Applying optimized settings..."
        sudo mkdir -p /etc/docker
        sudo cp /tmp/daemon.json /etc/docker/daemon.json
        sudo systemctl reload docker || warning "Could not reload Docker daemon"
    else
        warning "Sudo not available. Skipping Docker daemon optimization."
    fi
    
    success "Docker settings optimization completed"
}

# System optimization
optimize_system_settings() {
    log "Optimizing system settings for EdgeWatch..."
    
    # Optimize kernel parameters for networking
    cat > /tmp/edgewatch-sysctl.conf << EOF
# EdgeWatch network optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# File descriptor limits
fs.file-max = 1048576
EOF
    
    if command -v sudo >/dev/null 2>&1; then
        warning "System optimization requires sudo access. Applying kernel parameters..."
        sudo cp /tmp/edgewatch-sysctl.conf /etc/sysctl.d/99-edgewatch.conf
        sudo sysctl -p /etc/sysctl.d/99-edgewatch.conf || warning "Could not apply sysctl settings"
    else
        warning "Sudo not available. Skipping system optimization."
    fi
    
    success "System settings optimization completed"
}

# Container resource optimization
optimize_container_resources() {
    log "Optimizing container resource allocation..."
    
    # Calculate optimal resource allocation based on system specs
    local total_memory=$(free -m | awk '/^Mem:/{print $2}')
    local total_cpu=$(nproc)
    
    log "System specs: ${total_memory}MB RAM, ${total_cpu} CPU cores"
    
    # Calculate resource allocation (60% of system resources for EdgeWatch)
    local edgewatch_memory=$((total_memory * 60 / 100))
    local edgewatch_cpu=$((total_cpu * 60 / 100))
    
    if [ $edgewatch_cpu -lt 1 ]; then
        edgewatch_cpu=1
    fi
    
    log "Allocating ${edgewatch_memory}MB RAM and ${edgewatch_cpu} CPU cores to EdgeWatch"
    
    # Create optimized compose override
    cat > "$SCRIPT_DIR/docker-compose.optimized.yml" << EOF
version: '3.8'

services:
  edgewatch-primary:
    deploy:
      resources:
        limits:
          cpus: '${edgewatch_cpu}.0'
          memory: ${edgewatch_memory}M
        reservations:
          cpus: '0.5'
          memory: 512M
    environment:
      - PYTHONOPTIMIZE=2
      - MALLOC_TRIM_THRESHOLD_=131072
    ulimits:
      nofile:
        soft: 65536
        hard: 65536

  edgewatch-secondary:
    deploy:
      resources:
        limits:
          cpus: '${edgewatch_cpu}.0'
          memory: ${edgewatch_memory}M
        reservations:
          cpus: '0.5'
          memory: 512M
    environment:
      - PYTHONOPTIMIZE=2
      - MALLOC_TRIM_THRESHOLD_=131072
    ulimits:
      nofile:
        soft: 65536
        hard: 65536

  edgewatch-database:
    environment:
      - POSTGRES_SHARED_BUFFERS=256MB
      - POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
      - POSTGRES_MAINTENANCE_WORK_MEM=128MB
      - POSTGRES_CHECKPOINT_COMPLETION_TARGET=0.9
      - POSTGRES_WAL_BUFFERS=16MB
      - POSTGRES_DEFAULT_STATISTICS_TARGET=100

  edgewatch-redis:
    environment:
      - REDIS_MAXMEMORY=256MB
      - REDIS_MAXMEMORY_POLICY=allkeys-lru
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --save 900 1 --save 300 10 --save 60 10000

  edgewatch-nginx:
    environment:
      - NGINX_WORKER_PROCESSES=auto
      - NGINX_WORKER_CONNECTIONS=1024
EOF
    
    success "Container resource optimization completed"
}

# Build optimized images
build_optimized_images() {
    log "Building optimized production images..."
    
    cd "$PROJECT_ROOT"
    
    # Build production-optimized EdgeWatch image
    log "Building EdgeWatch production image..."
    docker build -t edgewatch:prod-optimized -f deployment/Dockerfile.prod .
    
    # Tag as latest production
    docker tag edgewatch:prod-optimized edgewatch:production
    
    success "Optimized images built successfully"
}

# Database optimization
optimize_database() {
    log "Applying database optimizations..."
    
    # Create PostgreSQL optimization configuration
    cat > "$SCRIPT_DIR/postgresql-optimized.conf" << EOF
# EdgeWatch PostgreSQL Optimizations

# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
work_mem = 16MB

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
max_wal_size = 2GB
min_wal_size = 1GB

# Query planner
default_statistics_target = 100
random_page_cost = 1.1

# Logging
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Connection settings
max_connections = 200
superuser_reserved_connections = 3

# Performance
synchronous_commit = off
full_page_writes = off
EOF
    
    success "Database optimization configuration created"
}

# Network optimization
optimize_networking() {
    log "Optimizing container networking..."
    
    # Create optimized network configuration
    cat > "$SCRIPT_DIR/docker-compose.network.yml" << EOF
version: '3.8'

networks:
  edgewatch-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_icc: "true"
      com.docker.network.bridge.enable_ip_masquerade: "true"
      com.docker.network.bridge.host_binding_ipv4: "0.0.0.0"
      com.docker.network.driver.mtu: "1500"
    ipam:
      driver: default
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1
EOF
    
    success "Network optimization completed"
}

# Monitoring optimization
optimize_monitoring() {
    log "Optimizing monitoring stack..."
    
    # Create Prometheus optimization configuration
    cat > "$SCRIPT_DIR/monitoring/prometheus-optimized.yml" << EOF
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  scrape_timeout: 10s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'edgewatch-primary'
    static_configs:
      - targets: ['edgewatch-primary:9090']
    scrape_interval: 15s
    metrics_path: '/metrics'

  - job_name: 'edgewatch-secondary'
    static_configs:
      - targets: ['edgewatch-secondary:9090']
    scrape_interval: 15s
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['edgewatch-database:5432']
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['edgewatch-redis:6379']
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['edgewatch-nginx:80']
    scrape_interval: 30s

storage:
  tsdb:
    retention.time: 30d
    retention.size: 10GB
EOF
    
    mkdir -p "$SCRIPT_DIR/monitoring"
    
    success "Monitoring optimization completed"
}

# Security optimization
optimize_security() {
    log "Applying security optimizations..."
    
    # Create security-optimized compose override
    cat > "$SCRIPT_DIR/docker-compose.security.yml" << EOF
version: '3.8'

services:
  edgewatch-primary:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE

  edgewatch-secondary:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE

  edgewatch-database:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  edgewatch-redis:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  edgewatch-prometheus:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m

  edgewatch-grafana:
    security_opt:
      - no-new-privileges:true

  edgewatch-nginx:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
      - CHOWN
      - SETGID
      - SETUID
EOF
    
    success "Security optimization completed"
}

# Performance testing
run_performance_tests() {
    log "Running performance tests..."
    
    # Create performance test script
    cat > /tmp/performance_test.sh << 'EOF'
#!/bin/bash

echo "=== EdgeWatch Performance Test ==="

# Test primary node response time
echo "Testing primary node..."
for i in {1..10}; do
    curl -w "@-" -o /dev/null -s "http://localhost:5000/health" <<< '%{time_total}\n'
done

# Test load handling
echo "Testing concurrent requests..."
ab -n 1000 -c 10 http://localhost:5000/health 2>/dev/null | grep "Requests per second"

echo "Performance test completed"
EOF
    
    chmod +x /tmp/performance_test.sh
    
    # Run performance test if services are running
    if curl -f http://localhost:5000/health >/dev/null 2>&1; then
        /tmp/performance_test.sh
    else
        warning "Services not running. Skipping performance tests."
    fi
    
    success "Performance testing completed"
}

# Main optimization function
main() {
    case "${1:-all}" in
        "docker")
            optimize_docker_settings
            ;;
        "system")
            optimize_system_settings
            ;;
        "containers")
            optimize_container_resources
            ;;
        "build")
            build_optimized_images
            ;;
        "database")
            optimize_database
            ;;
        "network")
            optimize_networking
            ;;
        "monitoring")
            optimize_monitoring
            ;;
        "security")
            optimize_security
            ;;
        "test")
            run_performance_tests
            ;;
        "all")
            log "Running complete production optimization..."
            optimize_docker_settings
            optimize_system_settings
            optimize_container_resources
            build_optimized_images
            optimize_database
            optimize_networking
            optimize_monitoring
            optimize_security
            success "Production optimization completed!"
            ;;
        *)
            echo "Usage: $0 {docker|system|containers|build|database|network|monitoring|security|test|all}"
            echo ""
            echo "Optimization options:"
            echo "  docker      - Optimize Docker daemon settings"
            echo "  system      - Optimize system kernel parameters"
            echo "  containers  - Optimize container resource allocation"
            echo "  build       - Build optimized production images"
            echo "  database    - Optimize database configuration"
            echo "  network     - Optimize container networking"
            echo "  monitoring  - Optimize monitoring stack"
            echo "  security    - Apply security optimizations"
            echo "  test        - Run performance tests"
            echo "  all         - Run all optimizations (default)"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
