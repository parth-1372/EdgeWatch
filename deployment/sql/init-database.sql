-- EdgeWatch Database Initialization Script
-- Creates the initial database schema for EdgeWatch monitoring system

-- Create database user and schema
CREATE USER IF NOT EXISTS edgewatch WITH PASSWORD 'edgewatch_secure_pass_2025';
GRANT ALL PRIVILEGES ON DATABASE edgewatch TO edgewatch;

-- Switch to EdgeWatch database
\c edgewatch;

-- Create schema
CREATE SCHEMA IF NOT EXISTS edgewatch;
SET search_path TO edgewatch, public;

-- Nodes table
CREATE TABLE IF NOT EXISTS nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET NOT NULL,
    port INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
    node_type VARCHAR(50) NOT NULL DEFAULT 'edge_server',
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE,
    UNIQUE(ip_address, port)
);

-- Metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    metric_type VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    INDEX (node_id, metric_type, timestamp),
    INDEX (timestamp)
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    rule_id UUID,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    INDEX (node_id, status),
    INDEX (created_at),
    INDEX (severity, status)
);

-- Alert rules table
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    operator VARCHAR(10) NOT NULL CHECK (operator IN ('gt', 'lt', 'eq', 'gte', 'lte')),
    threshold DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    enabled BOOLEAN DEFAULT true,
    node_filter JSONB DEFAULT '{}',
    notification_channels JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Gossip data table
CREATE TABLE IF NOT EXISTS gossip_data (
    id BIGSERIAL PRIMARY KEY,
    node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    data JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    INDEX (node_id, round),
    INDEX (timestamp)
);

-- Events table for audit trail
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source_node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    target_node_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
    event_data JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    INDEX (event_type, timestamp),
    INDEX (source_node_id),
    INDEX (timestamp)
);

-- System configuration table
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_metrics_node_time ON metrics(node_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_type_time ON metrics(metric_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status_time ON alerts(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gossip_node_round ON gossip_data(node_id, round DESC);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, timestamp DESC);

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add update timestamp triggers
CREATE TRIGGER update_nodes_timestamp
    BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_alert_rules_timestamp
    BEFORE UPDATE ON alert_rules
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_system_config_timestamp
    BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Insert default configuration values
INSERT INTO system_config (key, value, description) VALUES
    ('monitoring_interval', '30', 'Default monitoring interval in seconds'),
    ('gossip_interval', '30', 'Gossip protocol interval in seconds'),
    ('data_retention_days', '30', 'Number of days to retain metrics data'),
    ('alert_retention_days', '90', 'Number of days to retain alert history'),
    ('max_nodes', '1000', 'Maximum number of nodes to monitor'),
    ('cluster_mode', 'true', 'Enable cluster mode for high availability')
ON CONFLICT (key) DO NOTHING;

-- Create partitioning for metrics table (monthly partitions)
CREATE TABLE IF NOT EXISTS metrics_y2025m01 PARTITION OF metrics
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m02 PARTITION OF metrics
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m03 PARTITION OF metrics
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m04 PARTITION OF metrics
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m05 PARTITION OF metrics
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m06 PARTITION OF metrics
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m07 PARTITION OF metrics
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m08 PARTITION OF metrics
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m09 PARTITION OF metrics
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m10 PARTITION OF metrics
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m11 PARTITION OF metrics
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS metrics_y2025m12 PARTITION OF metrics
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA edgewatch TO edgewatch;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA edgewatch TO edgewatch;
GRANT USAGE ON SCHEMA edgewatch TO edgewatch;

-- Create sample data for testing
INSERT INTO nodes (name, ip_address, port, node_type, status) VALUES
    ('primary-node', '172.20.0.2', 5000, 'edgewatch_primary', 'online'),
    ('secondary-node', '172.20.0.3', 5000, 'edgewatch_secondary', 'online')
ON CONFLICT (ip_address, port) DO NOTHING;

COMMIT;
