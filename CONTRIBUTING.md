# Contributing to EdgeWatch

We're excited that you're interested in contributing to EdgeWatch! This guide will help you get started with contributing to our distributed edge monitoring platform.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Code Guidelines](#code-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

### Our Values

- **Respect**: Treat everyone with respect and kindness
- **Collaboration**: Work together towards common goals
- **Transparency**: Communicate openly and honestly
- **Excellence**: Strive for quality in all contributions
- **Learning**: Embrace learning and help others learn

## Getting Started

### Types of Contributions

We welcome various types of contributions:

- **Bug reports** and feature requests
- **Code contributions** (bug fixes, new features, optimizations)
- **Documentation** improvements
- **Testing** and quality assurance
- **Community support** and mentoring
- **Translations** and internationalization

### First-Time Contributors

If you're new to open source or EdgeWatch:

1. Look for issues labeled `good first issue` or `help wanted`
2. Start with documentation improvements
3. Fix small bugs or add minor features
4. Join our community discussions

## Development Setup

### Prerequisites

- **Git** for version control
- **Docker** and Docker Compose
- **Python 3.9+** and pip
- **Go 1.19+** (for core components)
- **Node.js 16+** (for web interface)

### Environment Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/edgewatch.git
   cd edgewatch
   git remote add upstream https://github.com/your-org/edgewatch.git
   ```

2. **Development Environment**
   ```bash
   # Setup development environment
   ./deployment/dev-setup.sh setup
   
   # Start development services
   ./deployment/dev-setup.sh start
   ```

3. **Verify Setup**
   ```bash
   # Check services are running
   curl http://localhost:5000/health
   
   # Run tests
   ./deployment/dev-setup.sh test
   ```

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "Add feature: description"

# Keep branch updated
git fetch upstream
git rebase upstream/main

# Push changes
git push origin feature/your-feature-name
```

## Contributing Process

### 1. Issue Discussion

Before starting work:

1. **Search existing issues** to avoid duplicates
2. **Create an issue** for new features or bugs
3. **Discuss approach** with maintainers
4. **Get approval** for significant changes

### 2. Development

1. **Create feature branch** from `main`
2. **Implement changes** following code guidelines
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Test thoroughly** in development environment

### 3. Pull Request

1. **Create pull request** with clear description
2. **Fill out PR template** completely
3. **Link related issues** using keywords
4. **Request review** from appropriate maintainers
5. **Address feedback** promptly

### Pull Request Template

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes (or clearly marked)
- [ ] All tests pass
```

## Code Guidelines

### General Principles

1. **Clarity over cleverness** - Write readable, maintainable code
2. **Consistency** - Follow existing patterns and conventions
3. **Documentation** - Comment complex logic and public interfaces
4. **Testing** - Write tests for all new functionality
5. **Performance** - Consider efficiency, especially in core components

### Python Code Style

```python
# Use PEP 8 style guidelines
import asyncio
import logging
from typing import Dict, List, Optional

class EdgeWatchMonitor:
    """Monitor for edge computing nodes.
    
    This class implements monitoring functionality for edge nodes,
    including health checks, metric collection, and alerting.
    """
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize monitor with configuration.
        
        Args:
            config: Configuration dictionary containing monitor settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    async def monitor_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Monitor a specific node and return metrics.
        
        Args:
            node_id: Unique identifier for the node to monitor
            
        Returns:
            Dictionary containing node metrics, or None if monitoring failed
            
        Raises:
            MonitoringError: If monitoring operation fails
        """
        try:
            # Implementation here
            pass
        except Exception as e:
            self.logger.error(f"Failed to monitor node {node_id}: {e}")
            raise MonitoringError(f"Monitoring failed for {node_id}") from e
```

### Go Code Style

```go
// Package edgewatch provides monitoring capabilities for edge computing environments.
package edgewatch

import (
    "context"
    "fmt"
    "time"
    
    "github.com/your-org/edgewatch/pkg/config"
    "github.com/your-org/edgewatch/pkg/logging"
)

// Monitor represents an edge computing monitor.
type Monitor struct {
    config *config.Config
    logger logging.Logger
}

// NewMonitor creates a new monitor instance.
func NewMonitor(cfg *config.Config) *Monitor {
    return &Monitor{
        config: cfg,
        logger: logging.NewLogger("monitor"),
    }
}

// MonitorNode monitors a specific node and returns metrics.
func (m *Monitor) MonitorNode(ctx context.Context, nodeID string) (*NodeMetrics, error) {
    m.logger.Info("Starting monitoring for node", "node_id", nodeID)
    
    // Implementation here
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
        // Monitoring logic
    }
    
    return &NodeMetrics{}, nil
}
```

### JavaScript/TypeScript Style

```typescript
// Use modern ES6+ features and TypeScript for type safety
import { EventEmitter } from 'events';

interface NodeMetrics {
  nodeId: string;
  timestamp: number;
  cpuUsage: number;
  memoryUsage: number;
  networkLatency?: number;
}

class EdgeWatchDashboard extends EventEmitter {
  private nodes: Map<string, NodeMetrics> = new Map();
  
  constructor(private config: DashboardConfig) {
    super();
  }
  
  /**
   * Add a new node to the dashboard
   * @param nodeId - Unique identifier for the node
   * @param metrics - Initial metrics for the node
   */
  public addNode(nodeId: string, metrics: NodeMetrics): void {
    this.nodes.set(nodeId, metrics);
    this.emit('nodeAdded', { nodeId, metrics });
  }
  
  /**
   * Update metrics for an existing node
   * @param nodeId - Node identifier
   * @param metrics - Updated metrics
   */
  public updateNode(nodeId: string, metrics: Partial<NodeMetrics>): void {
    const existing = this.nodes.get(nodeId);
    if (existing) {
      const updated = { ...existing, ...metrics };
      this.nodes.set(nodeId, updated);
      this.emit('nodeUpdated', { nodeId, metrics: updated });
    }
  }
}
```

### Git Commit Guidelines

Use conventional commits format:

```
type(scope): brief description

Detailed explanation of what and why, not how.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `perf`: Performance improvements
- `ci`: CI/CD changes

**Examples:**
```
feat(gossip): add adaptive message prioritization

Implement priority-based message filtering to reduce network overhead
in high-traffic scenarios. Messages are prioritized based on age,
type, and source node importance.

Closes #456

fix(api): handle connection timeout in node health checks

Add proper timeout handling and retry logic for node health check
requests to prevent hanging connections.

Fixes #789

docs(readme): update installation instructions

Update Docker installation steps and add troubleshooting section
for common setup issues.
```

## Testing

### Test Requirements

All contributions must include appropriate tests:

1. **Unit tests** for new functions and classes
2. **Integration tests** for API endpoints
3. **End-to-end tests** for critical user workflows
4. **Performance tests** for optimization changes

### Running Tests

```bash
# Run all tests
./deployment/dev-setup.sh test

# Run specific test suites
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/e2e/

# Run with coverage
python -m pytest --cov=src tests/

# Run performance tests
python -m pytest tests/performance/ -m performance
```

### Test Examples

```python
# Unit test example
import pytest
from unittest.mock import Mock, patch
from src.monitoring.collector import MetricsCollector

class TestMetricsCollector:
    def setup_method(self):
        self.config = {'interval': 30, 'enabled': True}
        self.collector = MetricsCollector(self.config)
        
    def test_collect_system_metrics(self):
        # Arrange
        expected_metrics = ['cpu_usage', 'memory_usage', 'disk_usage']
        
        # Act
        metrics = self.collector.collect_system_metrics()
        
        # Assert
        assert isinstance(metrics, dict)
        for metric in expected_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
            
    @patch('src.monitoring.collector.psutil.cpu_percent')
    def test_collect_cpu_usage(self, mock_cpu_percent):
        # Arrange
        mock_cpu_percent.return_value = 75.5
        
        # Act
        cpu_usage = self.collector.collect_cpu_usage()
        
        # Assert
        assert cpu_usage == 75.5
        mock_cpu_percent.assert_called_once()

# Integration test example
import pytest
import asyncio
from httpx import AsyncClient
from src.api.main import app

@pytest.mark.asyncio
class TestNodeAPI:
    async def test_create_node(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Arrange
            node_data = {
                "name": "test-node",
                "ip_address": "192.168.1.100",
                "port": 8080,
                "node_type": "edge_server"
            }
            
            # Act
            response = await client.post("/api/nodes", json=node_data)
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == node_data["name"]
            assert data["ip_address"] == node_data["ip_address"]
            
    async def test_get_node_health(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Act
            response = await client.get("/api/nodes/test-node/health")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "metrics" in data
```

### Test Data and Fixtures

```python
# conftest.py - Shared test fixtures
import pytest
import tempfile
import shutil
from src.database import Database
from src.config import Config

@pytest.fixture
def temp_database():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = f"{temp_dir}/test.db"
    db = Database(db_path)
    db.initialize()
    
    yield db
    
    db.close()
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return Config({
        'database': {'path': ':memory:'},
        'network': {'port': 0},  # Use random available port
        'monitoring': {'interval': 10}
    })

@pytest.fixture
def sample_nodes():
    """Provide sample node data for testing."""
    return [
        {
            'name': 'node-01',
            'ip_address': '192.168.1.101',
            'port': 8080,
            'node_type': 'edge_server'
        },
        {
            'name': 'node-02', 
            'ip_address': '192.168.1.102',
            'port': 8080,
            'node_type': 'iot_gateway'
        }
    ]
```

## Documentation

### Documentation Requirements

All contributions should include relevant documentation:

1. **Code comments** for complex logic
2. **API documentation** for new endpoints
3. **User documentation** for new features
4. **Architecture documentation** for design changes

### Documentation Style

```python
def calculate_network_priority(latency: float, packet_loss: float, bandwidth: float) -> float:
    """Calculate network priority score for gossip protocol routing.
    
    The priority score is used to determine the best paths for message
    propagation in the gossip network. Higher scores indicate better
    network conditions.
    
    Args:
        latency: Network latency in milliseconds (0-1000+)
        packet_loss: Packet loss percentage (0.0-1.0)
        bandwidth: Available bandwidth in Mbps (0-1000+)
        
    Returns:
        Priority score between 0.0 and 1.0, where 1.0 is the best
        
    Example:
        >>> calculate_network_priority(50.0, 0.01, 100.0)
        0.87
        
    Note:
        This function is called frequently during gossip protocol
        operation, so performance is critical.
    """
    # Normalize inputs to 0-1 range
    latency_score = max(0, 1 - min(latency / 200, 1))  # 200ms = 0 score
    loss_score = max(0, 1 - packet_loss)
    bandwidth_score = min(bandwidth / 100, 1)  # 100Mbps = 1.0 score
    
    # Weighted average (latency is most important)
    priority = (latency_score * 0.5 + loss_score * 0.3 + bandwidth_score * 0.2)
    
    return round(priority, 2)
```

### API Documentation

Use OpenAPI/Swagger format:

```yaml
# api/openapi.yaml
paths:
  /api/nodes:
    post:
      summary: Create a new monitoring node
      description: |
        Add a new node to the EdgeWatch monitoring system. The node
        will be automatically discovered and monitoring will begin.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/NodeCreate'
            example:
              name: "edge-server-01"
              ip_address: "192.168.1.100"
              port: 8080
              node_type: "edge_server"
              metadata:
                location: "Data Center A"
                environment: "production"
      responses:
        '201':
          description: Node created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Node'
        '400':
          description: Invalid input data
        '409':
          description: Node already exists

components:
  schemas:
    Node:
      type: object
      required:
        - id
        - name
        - ip_address
        - port
        - node_type
      properties:
        id:
          type: string
          format: uuid
          description: Unique node identifier
        name:
          type: string
          description: Human-readable node name
        ip_address:
          type: string
          format: ipv4
          description: Node IP address
        port:
          type: integer
          minimum: 1
          maximum: 65535
          description: Node port number
        node_type:
          type: string
          enum: [edge_server, iot_gateway, cdn_node, sensor]
          description: Type of node
        status:
          type: string
          enum: [online, offline, degraded]
          description: Current node status
        metadata:
          type: object
          description: Additional node metadata
```

## Community

### Getting Help

- **GitHub Discussions**: Ask questions and share ideas
- **Issue Tracker**: Report bugs and request features  
- **Documentation**: Check existing docs first
- **Code Review**: Get feedback on your changes

### Communication Guidelines

1. **Be respectful** and professional
2. **Be clear** and specific in communications
3. **Be patient** - maintainers are volunteers
4. **Be helpful** - assist other contributors
5. **Be constructive** in feedback and criticism

### Recognition

We recognize and appreciate all contributions:

- **Contributors** listed in CONTRIBUTORS.md
- **Release notes** mention significant contributions
- **Community highlights** in project updates
- **Maintainer status** for consistent, quality contributions

## Release Process

### Version Management

We use semantic versioning (SemVer):

- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

### Release Schedule

- **Major releases**: Quarterly
- **Minor releases**: Monthly
- **Patch releases**: As needed for critical fixes
- **Release candidates**: 1-2 weeks before major/minor releases

### Release Checklist

For maintainers preparing releases:

1. **Update version** numbers
2. **Update CHANGELOG.md** with release notes
3. **Run full test suite** and performance benchmarks
4. **Build and test** distribution packages
5. **Tag release** in Git
6. **Create GitHub release** with binaries
7. **Update documentation** for new version
8. **Announce release** to community

Thank you for contributing to EdgeWatch! Your help makes this project better for everyone. 🚀
