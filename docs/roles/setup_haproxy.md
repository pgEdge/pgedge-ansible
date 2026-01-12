# setup_haproxy

## Overview

Unlike most of the other roles in this collection, the `setup_haproxy` role installs **and** configures HAProxy as a load balancer for high availability PostgreSQL clusters. It provides intelligent routing to the current Patroni primary and optional routing to replicas using Patroni's REST API for health checks.

## Purpose

The role performs the following tasks:

- installs the HAProxy load balancer.
- configures health checks using the Patroni REST API.
- routes connections to the current Patroni primary.
- provides optional replica routing endpoints.
- enables the statistics dashboard.
- ensures high availability for database connections.
- handles automatic failover routing.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `setup_patroni`: The Patroni REST API must be available for routing to occur

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
    HAProxy is only useful for high availability deployments when you enable the `is_ha_cluster` parameter. Standalone PostgreSQL instances don't need load balancing.

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

This role is idempotent and safe to re-run. Subsequent executions will:

- delegate package installation to the operating system.
- regenerate configuration files each run to incorporate changes.
- always restart HAProxy to ensure configuration changes apply.

## Notes

You can access the statistics dashboard to monitor:

```bash
# From your browser
http://<haproxy-host>:7000/

# Or via curl
curl http://<haproxy-host>:7000/ | less
```
