# setup_haproxy

The `setup_haproxy` role installs and configures HAProxy as a load balancer
for high availability Postgres clusters. The role provides intelligent routing
to the current Patroni primary and optional routing to replicas using the
Patroni REST API for health checks.

The role performs the following tasks on inventory hosts:

- Install the HAProxy load balancer package from system repositories.
- Generate `haproxy.cfg` from a template with primary and replica listeners.
- Configure HTTP health checks against the Patroni REST API on port 8008.
- Restrict backend servers to nodes in the same zone as the HAProxy node.
- Enable the HAProxy statistics interface on port 7000.
- Start and enable the HAProxy service.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

Execute this role on haproxy hosts in high availability configurations before
running `setup_pgedge`. HAProxy must be configured before `setup_pgedge` runs
so that Spock subscriptions target the proxy layer, which ensures subscriptions
survive a Patroni failover without requiring manual resubscription.

In the following example, the playbook invokes the role on HAProxy hosts:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_port` | Postgres port for primary routing (default: 5432). |
| `haproxy_extra_routes` | Dictionary of additional routing endpoints. |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

The role installs HAProxy and configures routing to Postgres backends.

1. Install HAProxy from the distribution package repository with retry logic
   (up to five attempts, twenty-second delays, 300-second lock timeout).
2. Generate `/etc/haproxy/haproxy.cfg` with routing rules.
3. Start and enable the HAProxy service.

### Configuration Details

The generated configuration includes the following settings.

Global settings use `maxconn 100` for maximum concurrent connections.

Default settings use TCP mode with a 30-minute client and server timeout, a
4-second connection timeout, and a 5-second health check timeout.

The statistics dashboard listens on port 7000. Access the dashboard at
`http://<haproxy-host>:7000/`.

The primary cluster listener binds to `proxy_port` (default: 5432) and uses
HTTP health checks against the Patroni REST API on port 8008. HAProxy uses
the `on-marked-down shutdown-sessions` option to close existing connections
when a backend fails, which ensures the old primary does not accept further
writes after a failover.

### Extra Routes

The `haproxy_extra_routes` parameter adds additional routing endpoints for
read scaling. The following example configures replica and synchronous replica
routes:

```yaml
haproxy_extra_routes:
  replica:
    port: 5433
    lag: "10MB"
  sync:
    port: 5434
```

Each key matches a Patroni REST API endpoint check type. The optional `lag`
parameter filters replicas by maximum replication lag. The following common
endpoints are available:

- `/` returns 200 only on the primary.
- `/replica` returns 200 on replicas only.
- `/sync` returns 200 on synchronous replicas.
- `/async` returns 200 on asynchronous replicas.

## Usage Examples

In the following example, the playbook deploys HAProxy with default settings:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - init_server
    - setup_haproxy
```

In the following example, the playbook configures HAProxy with replica routing
that limits replication lag to 10 MB:

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

## Artifacts

This role generates the following file on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/haproxy/haproxy.cfg` | New | HAProxy configuration with routing rules and health checks. |

## Platform-Specific Behavior

On Debian-based systems, HAProxy version 2.6 or later is installed from APT
repositories and logs go to `/var/log/haproxy.log`. On RHEL-based systems,
HAProxy version 2.4 or later is installed from DNF repositories and logs are
accessible via `journalctl`.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
regenerates the configuration file to incorporate inventory changes and
restarts HAProxy to ensure configuration changes apply.

!!! info "Statistics Dashboard"
    The statistics interface on port 7000 provides real-time visibility into
    backend health, connection counts, and routing decisions.
