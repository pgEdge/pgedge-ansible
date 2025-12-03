# setup_haproxy

## Overview

Unlike most of the other roles in this collection, the `setup_haproxy` role installs **and** configures HAProxy as a load balancer for high availability PostgreSQL clusters. It provides intelligent routing to the current Patroni primary and optional routing to replicas using Patroni's REST API for health checks.

## Purpose

- Install HAProxy load balancer
- Configure health checks using Patroni REST API
- Route connections to current Patroni primary
- Provide optional replica routing endpoints
- Enable statistics dashboard
- Ensure high availability for database connections
- Handle automatic failover routing

## Role Dependencies

- `role_config` - Provides shared configuration variables
- `setup_patroni` - Patroni REST API must be available for routing to occur

## When to Use

Execute this role on **haproxy hosts** in high availability configurations after setting up Patroni:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - init_server
    - setup_haproxy
  when: is_ha_cluster
```

!!! note "HA Clusters Only"
    HAProxy is only useful for high availability deployments where `is_ha_cluster: true`. Standalone PostgreSQL instances don't need load balancing.

## Parameters

This role uses the following configuration parameters:

* `haproxy_extra_routes`
* `pg_port`

## Tasks Performed

### 1. HAProxy Package Installation

- Installs `haproxy` package from system repositories
- Includes retry logic (5 attempts, 20-second delays)
- Sets 300-second lock timeout for package manager
- Ensures HAProxy is available for configuration

### 2. Configuration Directory Creation

- Ensures `/etc/haproxy` directory exists
- Creates directory if not present (some systems create it with package)

### 3. HAProxy Configuration File Generation

Creates `/etc/haproxy/haproxy.cfg` with:

**Global Settings:**

- `maxconn 100` - Maximum concurrent connections

**Default Settings:**

- `mode tcp` - TCP mode for PostgreSQL connections
- `retries 2` - Connection retry attempts
- `timeout client 30m` - Client connection timeout (30 minutes)
- `timeout connect 4s` - Connection establishment timeout
- `timeout server 30m` - Server connection timeout
- `timeout check 5s` - Health check timeout

**Statistics Dashboard:**

- Listens on port 7000
- HTTP interface for monitoring
- URI: `http://<haproxy-host>:7000/`
- Shows backend status, connection stats, health check results

!!! info "Statistics Dashboard"
    The statistics interface on port 7000 provides real-time visibility into backend health, connection counts, and routing decisions. This is invaluable for troubleshooting. This output is in HTML format, so it's best to use a web browser.

**Primary Cluster Listener (`pg-cluster`):**

- Binds to port `proxy_port` (default: 5432)
- TCP mode for PostgreSQL protocol
- HTTP health check against Patroni REST API (port 8008)
- Expects HTTP 200 status (indicates Patroni primary)
- Backend servers: All nodes in `nodes_in_zone`
- Health check parameters:
    - `inter 3s` - Check interval
    - `fall 3` - Mark down after 3 failed checks
    - `rise 2` - Mark up after 2 successful checks
    - `on-marked-down shutdown-sessions` - Close sessions on failure

!!! important "Session Management"
    HAProxy uses `on-marked-down shutdown-sessions` to close existing connections when a backend fails. This ensures the old primary does not accept any further writes on a failover, and acts as a valuable fencing safeguard.

**Extra Route Listeners:**

For each route in `haproxy_extra_routes`:

- Binds to configured port (e.g., 5433 for replica)
- HTTP health check against Patroni REST API path (e.g., `/replica`)
- Optional lag parameter in health check query string
- Same backend server list as primary
- Same health check parameters

Common Patroni REST API responses:

- `/` - Returns 200 only on primary
- `/primary` - Same as `/`
- `/replica` - Returns 200 on replicas only
- `/read-only` - Returns 200 on read-only replicas (also primary)
- `/async` - Returns 200 on async replicas
- `/sync` - Returns 200 on synchronous replicas
- Additional `lag` parameter filters by replication lag

### 4. Service Management

- Enables HAProxy service for automatic startup
- Restarts HAProxy to apply configuration
- Ensures service is running and routing traffic

## Files Generated

### Configuration Files

- `/etc/haproxy/haproxy.cfg` - Main HAProxy configuration

### Log Files

HAProxy logs to syslog by default:

- Debian: `/var/log/haproxy.log`
- RHEL: `/var/log/messages` or `journalctl`

## Platform-Specific Behavior

### Debian-Family

- Installs HAProxy from APT repositories
- Version typically 2.6+
- Service name: `haproxy.service`

### RHEL-Family

- Installs HAProxy from DNF repositories
- Version typically 2.4+
- Service name: `haproxy.service`

## Example Usage

### Basic HAProxy Setup

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - init_server
    - setup_haproxy
```

### Custom Routing Configuration

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  vars:
    haproxy_extra_routes:
      replica:
        port: 5433
        lag: "10MB"
      sync:
        port: 5434
  roles:
    - setup_haproxy
```

## Idempotency

This role is fully idempotent:

- Package installation 
- Configuration file is regenerated each run (safe)
- Service restart ensures configuration applies
- Safe to re-run for configuration updates

## Troubleshooting

### HAProxy Service Fails to Start

**Symptom:** HAProxy service won't start

**Solution:**

- Check HAProxy logs:

```bash
# View logs
sudo journalctl -u haproxy -n 50 --no-pager

# Or on Debian
sudo tail -f /var/log/haproxy.log
```

- Validate configuration:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

- Check for port conflicts:

```bash
sudo netstat -tlnp | grep -E '5432|5433|7000'
```

### Health Checks Failing

**Symptom:** All backends marked as DOWN

**Solution:**

- Verify Patroni is running on PostgreSQL nodes:

```bash
sudo systemctl status patroni
```

- Test Patroni REST API manually:

```bash
curl http://pg-node:8008/
curl http://pg-node:8008/replica
```

- Check network connectivity:

```bash
telnet pg-node 8008
```

- Verify firewall allows port 8008:

```bash
# RHEL
sudo firewall-cmd --list-all

# Debian
sudo ufw status
```

### Cannot Connect Through HAProxy

**Symptom:** Database connections to HAProxy fail

**Solution:**

- Check HAProxy statistics:

```bash
curl http://haproxy-host:7000/
```

- Verify at least one backend is UP
- Test direct connection to backend:

```bash
psql -h pg-node -p 5432 -U admin
```

- Check HAProxy is listening:

```bash
sudo netstat -tlnp | grep haproxy
```

### Connections Route to Wrong Node

**Symptom:** HAProxy routes to replica instead of primary

**Solution:**

- Check Patroni cluster status:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yaml list
```

- Verify health check path:

```bash
# Primary should return 200
curl -I http://primary:8008/

# Replicas should return 503
curl -I http://replica:8008/
```

- Review HAProxy statistics dashboard (port 7000)

### Statistics Page Not Accessible

**Symptom:** Cannot access statistics on port 7000

**Solution:**

- Verify HAProxy is running
- Check firewall allows port 7000
- Test local access:

```bash
curl http://localhost:7000/
```

- Check bind address in configuration

### High Connection Latency

**Symptom:** Slow connection establishment through HAProxy

**Solution:**

- Check health check interval (may be too frequent)
- Verify network latency to backends:

```bash
ping pg-node
```

- Review HAProxy timeout settings
- Check backend server load
- Consider increasing `maxconn` limit

### Failover Not Working

**Symptom:** HAProxy doesn't route to new primary after failover

**Solution:**

- Verify health checks are working
- Check fall/rise parameters (may be too slow)
- Monitor Patroni failover:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yaml list
```

- Watch HAProxy logs during failover
- Verify new primary responds to health checks:

```bash
curl http://new-primary:8008/
```

## Notes

Access the statistics dashboard to monitor:

```bash
# From your browser
http://<haproxy-host>:7000/

# Or via curl
curl http://<haproxy-host>:7000/ | less
```

## See Also

- [Configuration Reference](../configuration.md) - HAProxy configuration variables
- [Architecture](../architecture.md) - Understanding HA cluster topology
- [setup_patroni](setup_patroni.md) - Provides REST API for health checks
