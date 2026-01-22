# setup_haproxy

The `setup_haproxy` role installs and configures HAProxy as a load balancer
for high availability Postgres clusters. The role provides intelligent routing
to the current Patroni primary and optional routing to replicas using the
Patroni REST API for health checks.

The role performs the following tasks on inventory hosts:

- Install the HAProxy load balancer package from system repositories.
- Configure health checks using the Patroni REST API.
- Route connections to the current Patroni primary for write operations.
- Provide optional replica routing endpoints for read scaling.
- Enable the statistics dashboard for monitoring and troubleshooting.
- Handle automatic failover routing when the primary changes.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_patroni` must be complete so the Patroni REST API is available.

## When to Use

Execute this role on haproxy hosts in high availability configurations after
setting up Patroni.

In the following example, the playbook invokes the role on HAProxy hosts:

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
    HAProxy is only useful for high availability deployments when you enable
    the `is_ha_cluster` parameter; standalone Postgres instances do not need
    load balancing.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
haproxy:
  vars:
    pg_port: 5432
    haproxy_extra_routes:
      replica:
        port: 5433
        lag: "10MB"
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `pg_port` | Postgres port for primary routing (default: 5432). |
| `haproxy_extra_routes` | Dictionary of additional routing endpoints. |

## How It Works

The role installs HAProxy and configures routing to Postgres backends.

### HAProxy Setup

When the role runs on haproxy hosts, it performs these steps:

1. Install the HAProxy package.
    - Install `haproxy` from system repositories.
    - Retry up to 5 attempts with 20-second delays on failure.
    - Set 300-second lock timeout for the package manager.

2. Create the configuration directory.
    - Ensure `/etc/haproxy` directory exists.
    - Some systems create the directory with the package.

3. Generate the HAProxy configuration file.
    - Create `/etc/haproxy/haproxy.cfg` with routing rules.
    - Configure global settings and default timeouts.
    - Set up the statistics dashboard on port 7000.
    - Configure primary cluster listener with Patroni health checks.
    - Add extra route listeners when `haproxy_extra_routes` is set.

4. Start the HAProxy service.
    - Enable HAProxy for automatic startup.
    - Restart HAProxy to apply the configuration.

### Configuration Details

The generated configuration file includes the following sections.

**Global Settings:**

- `maxconn 100` sets the maximum concurrent connections.

**Default Settings:**

- `mode tcp` enables TCP mode for Postgres connections.
- `retries 2` sets the connection retry attempts.
- `timeout client 30m` sets the client connection timeout.
- `timeout connect 4s` sets the connection establishment timeout.
- `timeout server 30m` sets the server connection timeout.
- `timeout check 5s` sets the health check timeout.

**Statistics Dashboard:**

- Listens on port 7000 for HTTP monitoring.
- Shows backend status, connection stats, and health check results.
- Access the dashboard at `http://<haproxy-host>:7000/`.

**Primary Cluster Listener:**

- Binds to `proxy_port` (default: 5432) for Postgres connections.
- Uses HTTP health checks against the Patroni REST API on port 8008.
- Expects HTTP 200 status to identify the Patroni primary.
- Backend servers include all nodes in `nodes_in_zone`.

**Health Check Parameters:**

- `inter 3s` sets the check interval.
- `fall 3` marks the server down after 3 failed checks.
- `rise 2` marks the server up after 2 successful checks.
- `on-marked-down shutdown-sessions` closes sessions on failure.

!!! important "Session Management"
    HAProxy uses `on-marked-down shutdown-sessions` to close existing
    connections when a backend fails; this ensures the old primary does not
    accept further writes on failover and acts as a valuable fencing safeguard.

### Extra Routes

The `haproxy_extra_routes` parameter configures additional routing endpoints
for read scaling or specialized routing.

In the following example, the configuration adds replica and sync routes:

```yaml
haproxy_extra_routes:
  replica:
    port: 5433
    lag: "10MB"
  sync:
    port: 5434
```

Common Patroni REST API endpoints for health checks include:

- `/` returns 200 only on the primary.
- `/replica` returns 200 on replicas only.
- `/read-only` returns 200 on read-only replicas and the primary.
- `/async` returns 200 on asynchronous replicas.
- `/sync` returns 200 on synchronous replicas.

The optional `lag` parameter filters replicas by replication lag.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic HAProxy Setup

In the following example, the playbook deploys HAProxy with default settings:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - init_server
    - setup_haproxy
```

### Custom Routing Configuration

In the following example, the playbook configures HAProxy with replica routing
that limits replication lag to 10MB:

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

### Full HA Deployment

In the following example, the playbook deploys a complete HA cluster with
HAProxy for load balancing:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - init_server
    - setup_haproxy

- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
  roles:
    - setup_postgres
    - setup_etcd
    - setup_patroni
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/haproxy/haproxy.cfg` | New | Main HAProxy configuration with routing rules and health checks. |

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems:

- The package manager installs HAProxy from APT repositories (version 2.6+).
- The service name is `haproxy.service`.
- The system writes logs to `/var/log/haproxy.log`.

### RHEL Family

On RHEL-based systems:

- The package manager installs HAProxy from DNF repositories (version 2.4+).
- The service name is `haproxy.service`.
- The system writes logs to `/var/log/messages` or makes them accessible via
  `journalctl`.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role may update these items on subsequent runs:

- Delegate package installation to the operating system package manager.
- Regenerate configuration files to incorporate inventory changes.
- Restart HAProxy to ensure configuration changes apply.

!!! info "Statistics Dashboard"
    The statistics interface on port 7000 provides real-time visibility into
    backend health, connection counts, and routing decisions; this output is
    in HTML format, so use a web browser for best results.
