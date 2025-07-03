"""
EdgeWatch Network Security Manager
Advanced networking and security configuration for EdgeWatch containers.
"""

import subprocess
import logging
import json
import ipaddress
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import re


class SecurityLevel(Enum):
    """Security levels for network configuration"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    HIGH_SECURITY = "high_security"


@dataclass
class NetworkPolicy:
    """Network security policy definition"""
    name: str
    source_networks: List[str]
    destination_ports: List[int]
    protocols: List[str]
    action: str  # ALLOW, DENY, LOG
    description: str


@dataclass
class FirewallRule:
    """Firewall rule definition"""
    chain: str
    target: str
    source: Optional[str] = None
    destination: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    comment: Optional[str] = None


class EdgeWatchNetworkSecurity:
    """
    Network security manager for EdgeWatch containers.
    Handles firewall rules, network policies, and security monitoring.
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.PRODUCTION):
        self.security_level = security_level
        self.logger = logging.getLogger(f"EdgeWatch.NetworkSecurity")
        
        # Network configuration
        self.edgewatch_network = "172.20.0.0/16"
        self.container_networks = {
            'edgewatch-primary': '172.20.0.10',
            'edgewatch-secondary': '172.20.0.11',
            'edgewatch-database': '172.20.0.20',
            'edgewatch-redis': '172.20.0.21',
            'edgewatch-prometheus': '172.20.0.30',
            'edgewatch-grafana': '172.20.0.31',
            'edgewatch-nginx': '172.20.0.40'
        }
        
        # Security policies
        self.network_policies = self._define_network_policies()
        self.firewall_rules = self._define_firewall_rules()
        
    def _define_network_policies(self) -> List[NetworkPolicy]:
        """Define network security policies based on security level"""
        policies = []
        
        if self.security_level in [SecurityLevel.PRODUCTION, SecurityLevel.HIGH_SECURITY]:
            # Strict production policies
            policies.extend([
                NetworkPolicy(
                    name="allow_api_access",
                    source_networks=["0.0.0.0/0"],
                    destination_ports=[5000, 5001],
                    protocols=["tcp"],
                    action="ALLOW",
                    description="Allow API access from anywhere"
                ),
                NetworkPolicy(
                    name="allow_dashboard_access",
                    source_networks=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
                    destination_ports=[8080, 8081],
                    protocols=["tcp"],
                    action="ALLOW",
                    description="Allow dashboard access from private networks"
                ),
                NetworkPolicy(
                    name="allow_monitoring_access",
                    source_networks=["172.20.0.0/16"],
                    destination_ports=[9000, 3000],
                    protocols=["tcp"],
                    action="ALLOW",
                    description="Allow monitoring access from EdgeWatch network"
                ),
                NetworkPolicy(
                    name="deny_database_external",
                    source_networks=["0.0.0.0/0"],
                    destination_ports=[5432],
                    protocols=["tcp"],
                    action="DENY",
                    description="Deny external database access"
                ),
                NetworkPolicy(
                    name="deny_redis_external",
                    source_networks=["0.0.0.0/0"],
                    destination_ports=[6379],
                    protocols=["tcp"],
                    action="DENY",
                    description="Deny external Redis access"
                )
            ])
        else:
            # Development/testing policies (more permissive)
            policies.extend([
                NetworkPolicy(
                    name="allow_all_dev",
                    source_networks=["0.0.0.0/0"],
                    destination_ports=[5000, 5001, 8080, 8081, 9000, 3000, 5432, 6379],
                    protocols=["tcp"],
                    action="ALLOW",
                    description="Allow all access for development"
                )
            ])
        
        return policies
    
    def _define_firewall_rules(self) -> List[FirewallRule]:
        """Define iptables firewall rules"""
        rules = []
        
        # Basic security rules
        rules.extend([
            # Allow loopback
            FirewallRule("INPUT", "ACCEPT", source="127.0.0.1", comment="Allow loopback"),
            
            # Allow established connections
            FirewallRule("INPUT", "ACCEPT", comment="Allow established connections"),
            
            # Allow EdgeWatch network traffic
            FirewallRule("INPUT", "ACCEPT", source=self.edgewatch_network, 
                        comment="Allow EdgeWatch network"),
        ])
        
        # Security level specific rules
        if self.security_level == SecurityLevel.HIGH_SECURITY:
            rules.extend([
                # Drop all other traffic
                FirewallRule("INPUT", "DROP", comment="Drop all other traffic"),
                
                # Log dropped packets
                FirewallRule("INPUT", "LOG", comment="Log dropped packets"),
            ])
        
        return rules
    
    def setup_container_network(self) -> bool:
        """Setup Docker network for EdgeWatch containers"""
        try:
            # Create EdgeWatch network if it doesn't exist
            network_name = "edgewatch-network"
            
            # Check if network exists
            result = subprocess.run(
                ["docker", "network", "ls", "--filter", f"name={network_name}", "--format", "{{.Name}}"],
                capture_output=True, text=True
            )
            
            if network_name not in result.stdout:
                # Create network
                cmd = [
                    "docker", "network", "create",
                    "--driver", "bridge",
                    "--subnet", self.edgewatch_network,
                    "--gateway", "172.20.0.1",
                    "--opt", "com.docker.network.bridge.enable_icc=true",
                    "--opt", "com.docker.network.bridge.enable_ip_masquerade=true",
                    "--opt", "com.docker.network.driver.mtu=1500",
                    network_name
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"Created EdgeWatch network: {network_name}")
                else:
                    self.logger.error(f"Failed to create network: {result.stderr}")
                    return False
            else:
                self.logger.info(f"EdgeWatch network already exists: {network_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up container network: {e}")
            return False
    
    def configure_firewall_rules(self) -> bool:
        """Configure iptables firewall rules"""
        try:
            # Check if we have iptables available
            result = subprocess.run(["which", "iptables"], capture_output=True)
            if result.returncode != 0:
                self.logger.warning("iptables not available, skipping firewall configuration")
                return True
            
            # Create EdgeWatch chain
            chain_name = "EDGEWATCH"
            subprocess.run(["iptables", "-N", chain_name], capture_output=True)
            
            # Flush existing EdgeWatch rules
            subprocess.run(["iptables", "-F", chain_name], capture_output=True)
            
            # Apply firewall rules
            for rule in self.firewall_rules:
                cmd = ["iptables", "-A", rule.chain, "-j", rule.target]
                
                if rule.source:
                    cmd.extend(["-s", rule.source])
                if rule.destination:
                    cmd.extend(["-d", rule.destination])
                if rule.port:
                    cmd.extend(["--dport", str(rule.port)])
                if rule.protocol:
                    cmd.extend(["-p", rule.protocol])
                if rule.comment:
                    cmd.extend(["-m", "comment", "--comment", rule.comment])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.warning(f"Failed to apply firewall rule: {result.stderr}")
            
            # Insert EdgeWatch chain into INPUT chain
            subprocess.run(["iptables", "-I", "INPUT", "-j", chain_name], capture_output=True)
            
            self.logger.info("Firewall rules configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error configuring firewall rules: {e}")
            return False
    
    def setup_network_monitoring(self) -> bool:
        """Setup network traffic monitoring"""
        try:
            # Create network monitoring configuration
            monitoring_config = {
                "interfaces": ["docker0", "br-*"],
                "protocols": ["tcp", "udp", "icmp"],
                "ports": [5000, 5001, 8080, 8081, 9000, 3000, 5432, 6379],
                "alert_thresholds": {
                    "connections_per_second": 100,
                    "bytes_per_second": 10485760,  # 10MB/s
                    "failed_connections": 50
                }
            }
            
            # Write monitoring configuration
            with open("/tmp/edgewatch_network_monitor.json", "w") as f:
                json.dump(monitoring_config, f, indent=2)
            
            self.logger.info("Network monitoring configuration created")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up network monitoring: {e}")
            return False
    
    def validate_network_security(self) -> Dict[str, Any]:
        """Validate network security configuration"""
        validation_results = {
            "network_isolation": False,
            "firewall_configured": False,
            "ssl_configured": False,
            "access_controls": False,
            "monitoring_enabled": False,
            "recommendations": []
        }
        
        try:
            # Check network isolation
            result = subprocess.run(
                ["docker", "network", "ls", "--filter", "name=edgewatch-network", "--format", "{{.Name}}"],
                capture_output=True, text=True
            )
            validation_results["network_isolation"] = "edgewatch-network" in result.stdout
            
            # Check firewall configuration
            result = subprocess.run(["iptables", "-L", "EDGEWATCH"], capture_output=True, text=True)
            validation_results["firewall_configured"] = result.returncode == 0
            
            # Check SSL certificate
            import os
            ssl_cert_path = "/etc/nginx/ssl/edgewatch.crt"
            validation_results["ssl_configured"] = os.path.exists(ssl_cert_path)
            
            # Generate recommendations
            if not validation_results["network_isolation"]:
                validation_results["recommendations"].append("Create dedicated Docker network for EdgeWatch")
            
            if not validation_results["firewall_configured"]:
                validation_results["recommendations"].append("Configure firewall rules for enhanced security")
            
            if not validation_results["ssl_configured"]:
                validation_results["recommendations"].append("Configure SSL/TLS certificates for encrypted communication")
            
            if self.security_level == SecurityLevel.DEVELOPMENT:
                validation_results["recommendations"].append("Consider upgrading to production security level")
            
        except Exception as e:
            self.logger.error(f"Error validating network security: {e}")
        
        return validation_results
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report"""
        report = {
            "timestamp": time.time(),
            "security_level": self.security_level.value,
            "network_configuration": {
                "edgewatch_network": self.edgewatch_network,
                "container_networks": self.container_networks
            },
            "policies": [
                {
                    "name": policy.name,
                    "action": policy.action,
                    "description": policy.description
                }
                for policy in self.network_policies
            ],
            "firewall_rules": len(self.firewall_rules),
            "validation": self.validate_network_security()
        }
        
        return report
    
    def apply_security_hardening(self) -> bool:
        """Apply security hardening measures"""
        try:
            success = True
            
            # Setup network
            if not self.setup_container_network():
                success = False
            
            # Configure firewall
            if not self.configure_firewall_rules():
                success = False
            
            # Setup monitoring
            if not self.setup_network_monitoring():
                success = False
            
            if success:
                self.logger.info("Security hardening applied successfully")
            else:
                self.logger.warning("Some security hardening measures failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error applying security hardening: {e}")
            return False


def create_network_security_manager(security_level: SecurityLevel = SecurityLevel.PRODUCTION) -> EdgeWatchNetworkSecurity:
    """Factory function to create network security manager"""
    return EdgeWatchNetworkSecurity(security_level)


# CLI interface
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="EdgeWatch Network Security Manager")
    parser.add_argument("--security-level", choices=['development', 'testing', 'production', 'high_security'],
                       default='production', help="Security level")
    parser.add_argument("--action", choices=['setup', 'validate', 'report', 'harden'],
                       default='setup', help="Action to perform")
    parser.add_argument("--format", choices=['json', 'text'], default='text', help="Output format")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create network security manager
    security_level = SecurityLevel(args.security_level)
    security_manager = create_network_security_manager(security_level)
    
    if args.action == "setup":
        success = security_manager.setup_container_network()
        sys.exit(0 if success else 1)
    elif args.action == "validate":
        results = security_manager.validate_network_security()
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print("Network Security Validation:")
            for key, value in results.items():
                if key != "recommendations":
                    print(f"  {key}: {'✓' if value else '✗'}")
            if results["recommendations"]:
                print("\nRecommendations:")
                for rec in results["recommendations"]:
                    print(f"  - {rec}")
    elif args.action == "report":
        report = security_manager.generate_security_report()
        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"EdgeWatch Security Report")
            print(f"Security Level: {report['security_level']}")
            print(f"Network: {report['network_configuration']['edgewatch_network']}")
            print(f"Policies: {len(report['policies'])}")
            print(f"Firewall Rules: {report['firewall_rules']}")
    elif args.action == "harden":
        success = security_manager.apply_security_hardening()
        sys.exit(0 if success else 1)
