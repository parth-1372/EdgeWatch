# EdgeWatch Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### Docker Not Found
```bash
Error: docker: command not found
```
**Solution:** Install Docker Desktop and ensure it's running.

#### Permission Denied
```bash
Error: permission denied while trying to connect to Docker daemon
```
**Solution:** Add user to docker group:
```bash
sudo usermod -aG docker $USER
# Logout and login again
```

### Deployment Issues

#### Container Startup Failures
```bash
Error: container edgewatch-primary exited with code 1
```
**Solution:** Check logs and configuration:
```bash
docker-compose logs edgewatch-primary
# Fix configuration in config/production.ini
```

#### Port Already in Use
```bash
Error: port 5000 already in use
```
**Solution:** Change ports in docker-compose.yml or stop conflicting services:
```bash
sudo lsof -i :5000
# Kill process or change port mapping
```

### Network Issues

#### Cannot Connect to Nodes
```bash
Error: connection refused to node 192.168.1.100:8080
```
**Solutions:**
1. Check firewall settings
2. Verify network connectivity
3. Ensure EdgeWatch is running on target node
4. Check port configuration

#### Gossip Protocol Not Working
```bash
Warning: No peers discovered in gossip network
```
**Solutions:**
1. Check gossip seeds configuration
2. Verify network reachability between nodes
3. Check firewall rules for gossip ports
4. Ensure all nodes have same network configuration

### Performance Issues

#### High Memory Usage
```bash
Warning: Memory usage above 90%
```
**Solutions:**
1. Increase container memory limits
2. Tune garbage collection settings
3. Reduce monitoring frequency
4. Archive old data

#### Slow Response Times
```bash
Warning: API response time > 5 seconds
```
**Solutions:**
1. Check database performance
2. Optimize queries
3. Increase worker processes
4. Check network latency

### Database Issues

#### Connection Failed
```bash
Error: could not connect to database
```
**Solutions:**
1. Check database container status
2. Verify connection string
3. Check database credentials
4. Ensure database is initialized

#### Migration Errors
```bash
Error: migration failed at version 003
```
**Solutions:**
1. Check database schema
2. Backup and restore database
3. Run migrations manually
4. Reset database if necessary

### Configuration Issues

#### Invalid Configuration
```bash
Error: invalid configuration key 'monitoring.invalid_key'
```
**Solution:** Check configuration syntax and valid keys in documentation.

#### Environment Variables Not Set
```bash
Warning: EDGEWATCH_DB_PATH not set, using default
```
**Solution:** Set required environment variables in .env file or docker-compose.yml.

### Monitoring Issues

#### Metrics Not Appearing
```bash
Warning: No metrics data for node edge-01
```
**Solutions:**
1. Check node connectivity
2. Verify metrics collection is enabled
3. Check firewall for metrics port
4. Restart monitoring services

#### Alerts Not Triggering
```bash
Warning: Alert rule not firing despite threshold breach
```
**Solutions:**
1. Check alert rule configuration
2. Verify notification settings
3. Check alert manager logs
4. Test notification channels

## Debugging Commands

### Check System Status
```bash
# Overall system status
./deployment/deploy.sh status

# Check all containers
docker-compose ps

# Check specific service logs
docker-compose logs edgewatch-primary

# Check resource usage
docker stats

# Check network connectivity
docker network ls
docker network inspect edgewatch-network
```

### Check Configuration
```bash
# Validate configuration
python -c "import configparser; c=configparser.ConfigParser(); c.read('config/production.ini'); print('Config OK')"

# Check environment variables
env | grep EDGEWATCH

# Test database connection
docker-compose exec edgewatch-database psql -U edgewatch -d edgewatch -c "\l"
```

### Performance Monitoring
```bash
# System resources
htop
iostat -x 1
free -h
df -h

# Network monitoring
netstat -tulpn
ss -tulpn

# Container monitoring
docker stats --no-stream
```

### Health Checks
```bash
# Application health
curl -f http://localhost:5000/health

# Database health
curl -f http://localhost:5000/health/database

# Metrics health
curl -f http://localhost:9090/-/healthy

# All services health
./deployment/deploy.sh health
```

## Recovery Procedures

### Database Recovery
```bash
# Stop services
docker-compose stop

# Backup current state
docker run --rm -v edgewatch_postgres_data:/source -v $(pwd)/backup:/backup alpine tar czf /backup/postgres_backup.tar.gz -C /source .

# Restore from backup
docker run --rm -v edgewatch_postgres_data:/target -v $(pwd)/backup:/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /target

# Start services
docker-compose start
```

### Configuration Reset
```bash
# Backup current configuration
cp config/production.ini config/production.ini.backup

# Reset to defaults
cp config/default.ini config/production.ini

# Restart services
docker-compose restart
```

### Complete Reset
```bash
# Stop and remove everything
docker-compose down -v --remove-orphans

# Remove images
docker rmi $(docker images "edgewatch*" -q)

# Clean up volumes
docker volume prune -f

# Redeploy
./deployment/deploy.sh deploy
```

## Log Analysis

### Common Log Patterns

#### Connection Issues
```
ERROR: Connection to node 192.168.1.100 failed: timeout
```
Action: Check network connectivity and firewall rules.

#### Database Errors
```
ERROR: Database query failed: connection lost
```
Action: Check database health and restart if necessary.

#### Memory Issues
```
WARNING: Memory usage 95%, consider increasing limits
```
Action: Monitor memory usage and increase container limits.

#### Gossip Issues
```
INFO: No gossip peers found, running in standalone mode
```
Action: Check gossip configuration and peer connectivity.

### Log Locations
- Application logs: `/var/log/edgewatch/`
- Container logs: `docker-compose logs`
- System logs: `/var/log/syslog`
- Database logs: Container logs for edgewatch-database

## Getting Additional Help

### Support Channels
- Documentation: [EdgeWatch Docs](README.md)
- GitHub Issues: [Report Issues](https://github.com/your-org/edgewatch/issues)
- Community: [Discussions](https://github.com/your-org/edgewatch/discussions)

### Diagnostic Information
When seeking help, include:
1. EdgeWatch version
2. Operating system and version
3. Docker and Docker Compose versions
4. Configuration files (sanitized)
5. Relevant log output
6. Steps to reproduce the issue

### Emergency Contacts
For critical production issues:
- Emergency hotline: +1-XXX-XXX-XXXX
- Email: emergency@your-org.com
- Slack: #edgewatch-emergency

---

*For additional support, consult the [API Reference](../api/reference.md) and [Developer Guide](../developer/development.md).*
