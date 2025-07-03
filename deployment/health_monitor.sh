#!/bin/bash

# EdgeWatch Container Health Monitoring Script
# Continuous health monitoring for EdgeWatch containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/health_check.py"

# Configuration
MONITORING_INTERVAL="${MONITORING_INTERVAL:-60}"  # seconds
ALERT_THRESHOLD="${ALERT_THRESHOLD:-3}"  # consecutive failures
LOG_FILE="${LOG_FILE:-./logs/health_monitor.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Initialize failure counters
declare -A failure_counts
declare -A last_alert_time

# Health monitoring function
monitor_health() {
    local service="$1"
    local current_time=$(date +%s)
    
    # Run health check
    if python3 "$HEALTH_CHECK_SCRIPT" --service "$service" --format json > /tmp/health_result.json 2>/dev/null; then
        # Health check passed
        local status=$(jq -r '.status' /tmp/health_result.json 2>/dev/null || echo "unknown")
        local response_time=$(jq -r '.response_time' /tmp/health_result.json 2>/dev/null || echo "0")
        
        if [ "$status" = "healthy" ]; then
            failure_counts["$service"]=0
            success "$service is healthy (${response_time}s)"
        elif [ "$status" = "degraded" ]; then
            warning "$service is degraded (${response_time}s)"
            failure_counts["$service"]=$((${failure_counts["$service"]:-0} + 1))
        else
            error "$service is unhealthy (${response_time}s)"
            failure_counts["$service"]=$((${failure_counts["$service"]:-0} + 1))
        fi
    else
        # Health check failed
        error "$service health check failed"
        failure_counts["$service"]=$((${failure_counts["$service"]:-0} + 1))
    fi
    
    # Check if we need to send alert
    local failure_count=${failure_counts["$service"]:-0}
    if [ "$failure_count" -ge "$ALERT_THRESHOLD" ]; then
        local last_alert=${last_alert_time["$service"]:-0}
        local alert_cooldown=3600  # 1 hour
        
        if [ $((current_time - last_alert)) -ge $alert_cooldown ]; then
            send_alert "$service" "$failure_count"
            last_alert_time["$service"]=$current_time
        fi
    fi
}

# Send alert function
send_alert() {
    local service="$1"
    local failure_count="$2"
    
    error "ALERT: $service has failed $failure_count consecutive health checks"
    
    # Send alert to monitoring system (placeholder)
    # In a real implementation, this would send alerts via email, Slack, etc.
    echo "ALERT: EdgeWatch service $service is unhealthy" | logger -t edgewatch-health
    
    # Attempt automatic recovery
    attempt_recovery "$service"
}

# Automatic recovery function
attempt_recovery() {
    local service="$1"
    
    log "Attempting recovery for $service"
    
    case "$service" in
        "primary_node"|"secondary_node")
            # Restart EdgeWatch containers
            log "Restarting EdgeWatch containers..."
            docker-compose -f "$SCRIPT_DIR/docker-compose.yml" restart edgewatch-primary edgewatch-secondary
            ;;
        "database")
            # Restart database container
            log "Restarting database container..."
            docker-compose -f "$SCRIPT_DIR/docker-compose.yml" restart edgewatch-database
            ;;
        "redis")
            # Restart Redis container
            log "Restarting Redis container..."
            docker-compose -f "$SCRIPT_DIR/docker-compose.yml" restart edgewatch-redis
            ;;
        "prometheus"|"grafana"|"nginx")
            # Restart monitoring containers
            log "Restarting monitoring containers..."
            docker-compose -f "$SCRIPT_DIR/docker-compose.yml" restart edgewatch-prometheus edgewatch-grafana edgewatch-nginx
            ;;
        *)
            warning "No recovery action defined for $service"
            ;;
    esac
}

# Main monitoring loop
main() {
    log "Starting EdgeWatch health monitoring"
    log "Monitoring interval: ${MONITORING_INTERVAL}s"
    log "Alert threshold: $ALERT_THRESHOLD consecutive failures"
    
    # Services to monitor
    services=(
        "primary_node"
        "secondary_node"
        "database"
        "redis"
        "prometheus"
        "grafana"
        "nginx"
        "system"
    )
    
    # Main monitoring loop
    while true; do
        log "Running health checks..."
        
        for service in "${services[@]}"; do
            monitor_health "$service"
        done
        
        # Run comprehensive health check
        if python3 "$HEALTH_CHECK_SCRIPT" --format json > /tmp/comprehensive_health.json 2>/dev/null; then
            local overall_status=$(jq -r '.summary.overall_status' /tmp/comprehensive_health.json 2>/dev/null || echo "unknown")
            local healthy_percentage=$(jq -r '.summary.healthy_percentage' /tmp/comprehensive_health.json 2>/dev/null || echo "0")
            
            log "Overall system status: $overall_status (${healthy_percentage}% healthy)"
        else
            error "Comprehensive health check failed"
        fi
        
        log "Health check cycle completed. Sleeping for ${MONITORING_INTERVAL}s..."
        sleep "$MONITORING_INTERVAL"
    done
}

# Signal handlers
cleanup() {
    log "Health monitoring stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start monitoring
main "$@"
