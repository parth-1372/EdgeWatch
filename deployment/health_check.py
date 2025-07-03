"""
EdgeWatch Container Health Check System
Comprehensive health monitoring for containerized EdgeWatch services.
"""

import requests
import time
import json
import logging
import psutil
import socket
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import subprocess
import os


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service: str
    status: HealthStatus
    response_time: float
    timestamp: datetime
    details: Dict[str, Any]
    error_message: Optional[str] = None


class ContainerHealthChecker:
    """
    Health checker for EdgeWatch containers.
    Monitors service availability, performance, and resource usage.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger("EdgeWatch.HealthChecker")
        
        # Health check configuration
        self.timeout = self.config.get('timeout', 10)
        self.retry_count = self.config.get('retry_count', 3)
        self.retry_delay = self.config.get('retry_delay', 1)
        
        # Service endpoints
        self.endpoints = {
            'primary_node': 'http://localhost:5000',
            'secondary_node': 'http://localhost:5001',
            'dashboard': 'http://localhost:8080',
            'prometheus': 'http://localhost:9000',
            'grafana': 'http://localhost:3000',
            'nginx': 'http://localhost:80'
        }
        
        # Database connection details
        self.database_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'edgewatch',
            'user': 'edgewatch'
        }
        
        # Redis connection details
        self.redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }
    
    def check_service_health(self, service: str, endpoint: str) -> HealthCheckResult:
        """Check health of a web service"""
        start_time = time.time()
        
        try:
            # Make health check request
            health_url = f"{endpoint}/health"
            response = requests.get(health_url, timeout=self.timeout)
            
            response_time = time.time() - start_time
            
            # Determine status based on response
            if response.status_code == 200:
                status = HealthStatus.HEALTHY
                details = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            elif response.status_code in [503, 502, 504]:
                status = HealthStatus.DEGRADED
                details = {'status_code': response.status_code, 'reason': response.reason}
            else:
                status = HealthStatus.UNHEALTHY
                details = {'status_code': response.status_code, 'reason': response.reason}
            
            return HealthCheckResult(
                service=service,
                status=status,
                response_time=response_time,
                timestamp=datetime.now(),
                details=details
            )
            
        except requests.exceptions.ConnectionError:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message="Connection refused"
            )
        except requests.exceptions.Timeout:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.DEGRADED,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message="Request timeout"
            )
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message=str(e)
            )
    
    def check_database_health(self) -> HealthCheckResult:
        """Check PostgreSQL database health"""
        start_time = time.time()
        
        try:
            import psycopg2
            
            conn = psycopg2.connect(
                host=self.database_config['host'],
                port=self.database_config['port'],
                database=self.database_config['database'],
                user=self.database_config['user'],
                connect_timeout=self.timeout
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            # Get database statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as connection_count,
                    pg_database_size(current_database()) as db_size
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """)
            
            connection_count, db_size = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service="database",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    'connection_count': connection_count,
                    'database_size': db_size,
                    'host': self.database_config['host'],
                    'port': self.database_config['port']
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="database",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message=str(e)
            )
    
    def check_redis_health(self) -> HealthCheckResult:
        """Check Redis health"""
        start_time = time.time()
        
        try:
            import redis
            
            r = redis.Redis(
                host=self.redis_config['host'],
                port=self.redis_config['port'],
                db=self.redis_config['db'],
                socket_timeout=self.timeout
            )
            
            # Test connection
            pong = r.ping()
            
            # Get Redis info
            info = r.info()
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service="redis",
                status=HealthStatus.HEALTHY if pong else HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    'ping_response': pong,
                    'version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory': info.get('used_memory'),
                    'uptime_in_seconds': info.get('uptime_in_seconds')
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="redis",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message=str(e)
            )
    
    def check_system_resources(self) -> HealthCheckResult:
        """Check system resource utilization"""
        start_time = time.time()
        
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network statistics
            network = psutil.net_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            if cpu_percent > 80 or memory.percent > 85 or disk.percent > 90:
                status = HealthStatus.DEGRADED
            if cpu_percent > 95 or memory.percent > 95 or disk.percent > 95:
                status = HealthStatus.UNHEALTHY
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service="system",
                status=status,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available': memory.available,
                    'disk_percent': disk.percent,
                    'disk_free': disk.free,
                    'network_bytes_sent': network.bytes_sent,
                    'network_bytes_recv': network.bytes_recv,
                    'process_count': process_count
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="system",
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message=str(e)
            )
    
    def check_container_health(self, container_name: str) -> HealthCheckResult:
        """Check Docker container health"""
        start_time = time.time()
        
        try:
            # Get container status using docker command
            result = subprocess.run(
                ['docker', 'inspect', container_name, '--format', '{{.State.Health.Status}}'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                return HealthCheckResult(
                    service=f"container_{container_name}",
                    status=HealthStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    timestamp=datetime.now(),
                    details={},
                    error_message="Container not found or not running"
                )
            
            health_status = result.stdout.strip()
            
            # Get additional container info
            info_result = subprocess.run(
                ['docker', 'inspect', container_name, '--format', '{{json .State}}'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            container_state = {}
            if info_result.returncode == 0:
                container_state = json.loads(info_result.stdout)
            
            # Map Docker health status to our status
            status_mapping = {
                'healthy': HealthStatus.HEALTHY,
                'unhealthy': HealthStatus.UNHEALTHY,
                'starting': HealthStatus.DEGRADED,
                'none': HealthStatus.UNKNOWN
            }
            
            status = status_mapping.get(health_status, HealthStatus.UNKNOWN)
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service=f"container_{container_name}",
                status=status,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    'health_status': health_status,
                    'running': container_state.get('Running', False),
                    'started_at': container_state.get('StartedAt'),
                    'pid': container_state.get('Pid'),
                    'restart_count': container_state.get('RestartCount', 0)
                }
            )
            
        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                service=f"container_{container_name}",
                status=HealthStatus.DEGRADED,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message="Health check timeout"
            )
        except Exception as e:
            return HealthCheckResult(
                service=f"container_{container_name}",
                status=HealthStatus.UNKNOWN,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                details={},
                error_message=str(e)
            )
    
    def run_comprehensive_health_check(self) -> Dict[str, HealthCheckResult]:
        """Run comprehensive health check on all services"""
        results = {}
        
        # Check web services
        for service, endpoint in self.endpoints.items():
            self.logger.info(f"Checking health of {service}")
            results[service] = self.check_service_health(service, endpoint)
        
        # Check database
        self.logger.info("Checking database health")
        results['database'] = self.check_database_health()
        
        # Check Redis
        self.logger.info("Checking Redis health")
        results['redis'] = self.check_redis_health()
        
        # Check system resources
        self.logger.info("Checking system resources")
        results['system'] = self.check_system_resources()
        
        # Check containers
        containers = [
            'edgewatch-primary',
            'edgewatch-secondary',
            'edgewatch-database',
            'edgewatch-redis',
            'edgewatch-prometheus',
            'edgewatch-grafana',
            'edgewatch-nginx'
        ]
        
        for container in containers:
            self.logger.info(f"Checking container {container}")
            results[f"container_{container}"] = self.check_container_health(container)
        
        return results
    
    def get_health_summary(self, results: Dict[str, HealthCheckResult]) -> Dict[str, Any]:
        """Get summary of health check results"""
        status_counts = {
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0,
            'unknown': 0
        }
        
        total_response_time = 0
        service_count = len(results)
        
        for result in results.values():
            status_counts[result.status.value] += 1
            total_response_time += result.response_time
        
        # Overall system status
        if status_counts['unhealthy'] > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif status_counts['degraded'] > 0:
            overall_status = HealthStatus.DEGRADED
        elif status_counts['unknown'] > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            'overall_status': overall_status.value,
            'total_services': service_count,
            'status_counts': status_counts,
            'average_response_time': total_response_time / service_count if service_count > 0 else 0,
            'timestamp': datetime.now().isoformat(),
            'healthy_percentage': (status_counts['healthy'] / service_count * 100) if service_count > 0 else 0
        }


def create_health_checker(config: Optional[Dict[str, Any]] = None) -> ContainerHealthChecker:
    """Factory function to create health checker"""
    return ContainerHealthChecker(config)


# CLI interface for health checking
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="EdgeWatch Container Health Checker")
    parser.add_argument("--service", help="Check specific service")
    parser.add_argument("--format", choices=['json', 'text'], default='text', help="Output format")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create health checker
    health_checker = create_health_checker({'timeout': args.timeout})
    
    if args.service:
        # Check specific service
        if args.service in health_checker.endpoints:
            result = health_checker.check_service_health(args.service, health_checker.endpoints[args.service])
        elif args.service == 'database':
            result = health_checker.check_database_health()
        elif args.service == 'redis':
            result = health_checker.check_redis_health()
        elif args.service == 'system':
            result = health_checker.check_system_resources()
        elif args.service.startswith('container_'):
            container_name = args.service.replace('container_', '')
            result = health_checker.check_container_health(container_name)
        else:
            print(f"Unknown service: {args.service}")
            sys.exit(1)
        
        if args.format == 'json':
            print(json.dumps({
                'service': result.service,
                'status': result.status.value,
                'response_time': result.response_time,
                'timestamp': result.timestamp.isoformat(),
                'details': result.details,
                'error_message': result.error_message
            }, indent=2))
        else:
            print(f"Service: {result.service}")
            print(f"Status: {result.status.value}")
            print(f"Response Time: {result.response_time:.3f}s")
            print(f"Timestamp: {result.timestamp}")
            if result.error_message:
                print(f"Error: {result.error_message}")
            if result.details:
                print(f"Details: {result.details}")
    else:
        # Run comprehensive health check
        results = health_checker.run_comprehensive_health_check()
        summary = health_checker.get_health_summary(results)
        
        if args.format == 'json':
            output = {
                'summary': summary,
                'services': {}
            }
            for service, result in results.items():
                output['services'][service] = {
                    'status': result.status.value,
                    'response_time': result.response_time,
                    'timestamp': result.timestamp.isoformat(),
                    'details': result.details,
                    'error_message': result.error_message
                }
            print(json.dumps(output, indent=2))
        else:
            print(f"Overall Status: {summary['overall_status']}")
            print(f"Healthy Services: {summary['status_counts']['healthy']}/{summary['total_services']}")
            print(f"Degraded Services: {summary['status_counts']['degraded']}")
            print(f"Unhealthy Services: {summary['status_counts']['unhealthy']}")
            print(f"Average Response Time: {summary['average_response_time']:.3f}s")
            print(f"Health Percentage: {summary['healthy_percentage']:.1f}%")
            print("\nService Details:")
            for service, result in results.items():
                status_icon = {
                    'healthy': '✓',
                    'degraded': '⚠',
                    'unhealthy': '✗',
                    'unknown': '?'
                }.get(result.status.value, '?')
                print(f"  {status_icon} {service}: {result.status.value} ({result.response_time:.3f}s)")
                if result.error_message:
                    print(f"    Error: {result.error_message}")
    
    # Exit with appropriate code
    if args.service:
        sys.exit(0 if result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else 1)
    else:
        sys.exit(0 if summary['overall_status'] in ['healthy', 'degraded'] else 1)
