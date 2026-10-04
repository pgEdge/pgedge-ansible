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
| `pgedge_seed_zone` | Zone the other zones copy their data from (HA only). |
| `pgedge_seed_stall_minutes` | Give up on the copy from the seed zone after this long without progress (default: 15). |
| `pgedge_seed_max_hours` | Longest the copy from the seed zone may take (default: 24). |

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

### Seeding From One Zone

Every subscription the role creates normally copies nothing, because every
zone starts empty. When one zone already holds the cluster's data and the
others are empty, set `pgedge_seed_zone` to that zone. Each other zone then
subscribes to the seed zone with `synchronize_structure` and
`synchronize_data`, and waits for the copy to finish, before the role creates
any other subscription. The recovery playbook uses this to refill the zones it
rebuilds from the zone it restored.

The wait for the copy does not use `spock.sub_wait_for_sync()`, which keeps
waiting while Spock restarts a copy that has failed. It polls
`spock.sub_show_status()` and `spock.local_sync_status` instead, and succeeds
once the subscription is `replicating` and every table is ready. It fails
immediately if the subscription is `disabled`. It also fails if the
subscription stays `down` for two minutes, as it does after a bad provider DSN
or password, or a copy that broke partway; Spock 5 does not resume a copy that
broke after it started. Last, it fails if nothing has moved for
`pgedge_seed_stall_minutes`. Movement is any change in the sync step, in the
tables left to sync, in the database's size, or in the progress Postgres reports
for the COPY and index builds. The failure message shows the subscription's
status, the tables not yet synced, and the Spock lines from the end of the
Postgres log. `pgedge_seed_max_hours` is a backstop for the whole wait.

The copy runs once. A later run finds the subscription and leaves it alone, so
the setting does no harm if it stays in place.

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
