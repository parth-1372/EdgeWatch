# EdgeWatch Developer Guide

## Architecture Overview

EdgeWatch is built with a modular, scalable architecture designed for monitoring distributed edge computing infrastructure.

### Core Components

```
EdgeWatch/
├── src/
│   ├── core/           # Main daemon and orchestration
│   ├── communication/  # Gossip protocol and networking
│   ├── storage/        # Database and persistence
│   ├── monitoring/     # Metrics collection and analysis
│   ├── api/           # REST API and web interface
│   └── experiments/   # Research and experimentation tools
├── config/            # Configuration management
├── deployment/        # Docker and deployment tools
└── docs/             # Documentation
```

### Key Design Principles

1. **Modularity:** Each component is independently testable and replaceable
2. **Scalability:** Gossip-based communication for distributed coordination
3. **Reliability:** Fault-tolerant design with graceful degradation
4. **Extensibility:** Plugin architecture for custom monitors and alerts
5. **Performance:** Optimized for low-latency, high-throughput environments

## Development Environment Setup

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Git
- Your favorite IDE (VS Code recommended)

### Setup Instructions

```bash
# Clone the repository
git clone https://github.com/yourusername/EdgeWatch.git
cd EdgeWatch

# Create development environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
python -m pytest tests/
```

### Development Configuration

Create `config/development.ini`:

```ini
[logging]
level = DEBUG
console = true
file = logs/edgewatch-dev.log

[database]
path = data/edgewatch-dev.db
echo = true

[api]
debug = true
reload = true
```

## Code Organization

### Core Module (`src/core/`)

The core module contains the main daemon and orchestration logic:

- `daemon.py`: Main EdgeWatch daemon
- `node.py`: Node representation and management
- `coordinator.py`: System coordination and state management

### Communication Module (`src/communication/`)

Handles all networking and inter-node communication:

- `gossip.py`: Gossip protocol implementation
- `optimizer.py`: Communication optimization algorithms
- `protocol.py`: Network protocol definitions

### Storage Module (`src/storage/`)

Data persistence and management:

- `database.py`: Database abstraction layer
- `models.py`: Data models and schema
- `analytics.py`: Data analysis and aggregation

### Monitoring Module (`src/monitoring/`)

Metrics collection and analysis:

- `collector.py`: Metrics collection engine
- `analyzer.py`: Real-time analysis and anomaly detection
- `alerting.py`: Alert generation and notification

## Development Workflow

### Git Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit frequently
3. Write tests for new functionality
4. Update documentation
5. Submit pull request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for all public functions
- Write comprehensive docstrings
- Maintain test coverage above 80%

### Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src tests/

# Run specific test file
python -m pytest tests/test_daemon.py

# Run integration tests
python -m pytest tests/integration/
```

### Code Quality Tools

```bash
# Linting
flake8 src/ tests/
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

## Adding New Features

### 1. Create a New Monitor

```python
# src/monitoring/monitors/custom_monitor.py
from typing import Dict, Any
from ..base import BaseMonitor

class CustomMonitor(BaseMonitor):
    """Custom monitoring implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "custom_monitor"
    
    async def collect_metrics(self) -> Dict[str, float]:
        """Collect custom metrics."""
        # Implementation here
        return {
            "custom_metric_1": 42.0,
            "custom_metric_2": 3.14
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate monitor configuration."""
        required_fields = ["target_host", "check_interval"]
        return all(field in config for field in required_fields)
```

### 2. Create a New API Endpoint

```python
# src/api/routes/custom.py
from fastapi import APIRouter, Depends
from ..auth import get_current_user
from ..models import CustomResponse

router = APIRouter(prefix="/custom", tags=["custom"])

@router.get("/endpoint", response_model=CustomResponse)
async def custom_endpoint(user=Depends(get_current_user)):
    """Custom API endpoint."""
    # Implementation here
    return CustomResponse(data="custom_data")
```

### 3. Add Configuration Options

```python
# src/config/schema.py
@dataclass
class CustomConfig:
    """Custom feature configuration."""
    enabled: bool = False
    custom_setting: str = "default_value"
    custom_timeout: int = 30

# config/default.ini
[custom]
enabled = false
custom_setting = production_value
custom_timeout = 60
```

## Database Schema

### Core Tables

```sql
-- Nodes table
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    ip_address TEXT NOT NULL,
    port INTEGER NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT DEFAULT 'unknown',
    last_seen TIMESTAMP,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Metrics table
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    node_id INTEGER REFERENCES nodes(id),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    labels JSON
);

-- Alerts table
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    node_id INTEGER REFERENCES nodes(id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);
```

### Adding New Tables

```python
# src/storage/migrations/001_add_custom_table.py
"""Add custom table for new feature."""

def upgrade(connection):
    connection.execute("""
        CREATE TABLE custom_data (
            id INTEGER PRIMARY KEY,
            node_id INTEGER REFERENCES nodes(id),
            custom_field TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def downgrade(connection):
    connection.execute("DROP TABLE custom_data")
```

## API Development

### Authentication

EdgeWatch uses JWT-based authentication:

```python
from src.api.auth import create_access_token, verify_token

# Create token
token = create_access_token(user_id="admin")

# Verify token
user = verify_token(token)
```

### Request/Response Models

```python
from pydantic import BaseModel
from typing import List, Optional

class NodeRequest(BaseModel):
    name: str
    ip_address: str
    port: int
    node_type: str
    metadata: Optional[dict] = None

class NodeResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    port: int
    node_type: str
    status: str
    last_seen: Optional[datetime]
    metadata: Optional[dict]
```

### Error Handling

```python
from fastapi import HTTPException
from src.api.exceptions import EdgeWatchException

@router.post("/nodes")
async def create_node(node: NodeRequest):
    try:
        # Implementation
        pass
    except EdgeWatchException as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Testing Guidelines

### Unit Tests

```python
# tests/test_daemon.py
import pytest
from src.core.daemon import EdgeWatchDaemon

class TestEdgeWatchDaemon:
    @pytest.fixture
    def daemon(self):
        return EdgeWatchDaemon(config_path="config/testing.ini")
    
    def test_daemon_initialization(self, daemon):
        assert daemon.is_initialized
        assert daemon.config is not None
    
    @pytest.mark.asyncio
    async def test_daemon_start_stop(self, daemon):
        await daemon.start()
        assert daemon.is_running
        
        await daemon.stop()
        assert not daemon.is_running
```

### Integration Tests

```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient
from src.api.main import app

@pytest.mark.asyncio
async def test_create_node():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/nodes", json={
            "name": "test-node",
            "ip_address": "192.168.1.100",
            "port": 8080,
            "node_type": "edge_server"
        })
        assert response.status_code == 201
        assert response.json()["name"] == "test-node"
```

### Mock External Dependencies

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_gossip_protocol():
    mock = AsyncMock()
    mock.broadcast.return_value = True
    mock.receive.return_value = {"type": "heartbeat"}
    return mock
```

## Performance Optimization

### Profiling

```python
# Use cProfile for performance analysis
python -m cProfile -o profile.stats src/core/daemon.py

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats
```

### Memory Management

```python
# Use memory profilers
pip install memory-profiler
@profile
def memory_intensive_function():
    # Function implementation
    pass
```

### Async Best Practices

```python
import asyncio
from typing import List

async def process_nodes_concurrently(nodes: List[Node]):
    """Process multiple nodes concurrently."""
    tasks = []
    for node in nodes:
        task = asyncio.create_task(process_single_node(node))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## Debugging

### Logging Configuration

```python
import logging
from src.config import get_logger

logger = get_logger(__name__)

# Use structured logging
logger.info("Node status changed", extra={
    "node_id": node.id,
    "old_status": old_status,
    "new_status": new_status,
    "timestamp": datetime.utcnow().isoformat()
})
```

### Debug Mode

```bash
# Run with debug logging
EDGEWATCH_LOG_LEVEL=DEBUG python src/core/daemon.py

# Enable API debug mode
EDGEWATCH_DEBUG=true python src/api/main.py
```

## Contributing

### Code Review Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Performance impact considered
- [ ] Security implications reviewed
- [ ] Backward compatibility maintained

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Documentation
- [ ] Code documentation updated
- [ ] User documentation updated
- [ ] API documentation updated
```

## Resources

- [Python AsyncIO Documentation](https://docs.python.org/3/library/asyncio.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Docker Best Practices](https://docs.docker.com/develop/best-practices/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
