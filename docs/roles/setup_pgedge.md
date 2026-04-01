# setup_pgedge

The `setup_pgedge` role configures Spock logical replication to initialize a
multi-master Postgres cluster. The role establishes Spock nodes and
subscriptions between all applicable Postgres instances, enabling bidirectional
data synchronization across zones and nodes.

The role performs the following tasks on inventory hosts:

- Create a Spock node named `edge[ZONE]` with the appropriate connection string.
- Set the Spock exception behavior to the value of `exception_behaviour`.
- Set the Snowflake node ID to the zone number.
- Enable DDL replication via Spock.
- Subscribe the current node to every other zone in the cluster.

In HA clusters, the role runs only on the first node in each zone.
Subscriptions target the HAProxy node in the remote zone when one is
available.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_postgres` installs Postgres with the Spock extension.
- `setup_patroni` must be complete in HA clusters so Patroni manages the
  primary node.
- `setup_haproxy` must be complete in HA clusters so subscriptions target
  the proxy layer.

!!! info "Role Order"
    In HA clusters, execute this role after `setup_haproxy`. Spock
    subscriptions target HAProxy so that replication continues after a
    Patroni failover without requiring manual resubscription.

## When to Use

Execute this role on all pgedge hosts after Postgres setup to establish
multi-master replication.

In the following example, the playbook invokes the role for standalone nodes:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - setup_pgedge
```

For HA clusters, the following example invokes the role after HAProxy setup:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy

- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_pgedge
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `db_names` | Databases to configure for Spock replication. |
| `pg_port` | Postgres port for direct node connections. |
| `zone` | Zone identifier for multi-zone deployments. |
| `pgedge_user` | pgEdge user for node-to-node communication. |
| `pgedge_password` | Password for the pgEdge user account. |
| `proxy_node` | Specific proxy hostname for HA deployments. |
| `proxy_port` | Proxy port for HA deployments (default: 5432). |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

The role creates Spock nodes and subscriptions based on whether the cluster
uses HA mode.

### Standalone Deployment

When `is_ha_cluster` is `false`, the role creates direct node-to-node
connections. It creates a Spock node named `edge{{ zone }}` on each node and
subscribes each node to every other node, resulting in a full mesh topology
where all nodes replicate to all other nodes.

### HA Deployment

When `is_ha_cluster` is `true`, the role creates zone-based connections
through HAProxy. It creates Spock nodes only on the first node in each zone
and subscribes each zone to every other zone. The subscription connection
target is selected in the following priority order:

1. The `proxy_node` variable, if set.
2. The first HAProxy node in the remote zone.
3. The first pgEdge node in the remote zone, as a fallback.

The `proxy_port` parameter controls the port used for these connections,
allowing HAProxy to run on a pgEdge node rather than a dedicated host.

### Subscription Synchronization

After creating subscriptions, the role waits for initial synchronization
using the `spock.sub_wait_for_sync()` function. For large databases, this
can take considerable time.

!!! warning "Subscription Names"
    Subscription names follow the format `sub_n{{ zone }}_n{{ remote_zone }}`.
    Changing zone assignments after initial setup can cause subscription
    conflicts or render the cluster inoperable.

## Usage Examples

In the following example, the playbook deploys a standalone multi-master
cluster with two databases:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    db_names:
      - production
      - analytics
  roles:
    - setup_postgres
    - setup_pgedge
```

In the following example, the playbook specifies a custom proxy for
replication connections:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    proxy_node: "haproxy.example.com"
    proxy_port: 5000
  roles:
    - setup_pgedge
```

## Artifacts

This role modifies the following file and creates database objects on each
configured database:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `~postgres/.pgpass` | Modified | Password file entry for pgedge user authentication. |

The role also creates the following database objects in each configured
database:

| Object | Location | Purpose |
|--------|----------|---------|
| Spock nodes | `spock.node` table | Node metadata with node_id and node_name. |
| Spock subscriptions | `spock.subscription` table | Subscription metadata with sub_id and sub_name. |
| Replication slots | System catalog | Logical replication slots for each subscription. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role checks
whether Spock nodes and subscriptions exist before creating them.

!!! warning "Subscription Changes"
    Adding new nodes or databases requires re-running this role on all nodes
    to establish the new subscriptions.
