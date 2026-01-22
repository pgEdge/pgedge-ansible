# setup_pgedge

The `setup_pgedge` role configures Spock logical replication to initialize a
multi-master Postgres cluster. The role establishes Spock nodes and
subscriptions between all applicable Postgres instances, enabling bidirectional
data synchronization across zones and nodes.

The role performs the following tasks on inventory hosts:

- Configure password authentication for `pgedge_user` via `.pgpass`.
- Create Spock node metadata on each Postgres instance.
- Establish Spock subscriptions between all nodes or zone leaders.
- Configure multi-master logical replication topology.
- Support both direct node-to-node and proxy-based subscriptions.
- Verify subscription synchronization before completing.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_postgres` installs Postgres with the Spock extension.
- `setup_patroni` manages HA clusters (optional, for HA deployments).
- `setup_haproxy` provides proxy routing for HA clusters (optional).

!!! info "Role Order"
    When deploying an HA cluster, execute this role after `setup_patroni` and
    `setup_haproxy`; Patroni determines the primary writable node in each
    zone, and HAProxy ensures this node receives Spock inter-node traffic.

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

For HA clusters, the following example invokes the role after HAProxy and
Patroni setup:

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
    - setup_patroni
    - setup_pgedge
```

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    db_names:
      - production
      - analytics
    pgedge_user: pgedge
    pgedge_password: "{{ vault_pgedge_password }}"
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `db_names` | Databases to configure for Spock replication. |
| `pg_port` | Postgres port for direct node connections. |
| `zone` | Zone identifier for multi-zone deployments. |
| `pgedge_user` | pgEdge user for node communication. |
| `pgedge_password` | Password for the pgEdge user account. |
| `proxy_node` | Specific proxy hostname for HA deployments. |
| `proxy_port` | Proxy port for HA deployments (default: 5432). |

## How It Works

The role configures Spock replication based on the deployment type.

### User Access Configuration

On all nodes, the role performs this initial step:

1. Configure user access.
    - Create a `.pgpass` entry for `pgedge_user`.
    - Store credentials in `~postgres/.pgpass` with mode 600.
    - Enable automated authentication for Spock connections.

### Standalone Deployment

When `is_ha_cluster` is `false`, the role creates direct node-to-node
connections:

1. Create Spock nodes.
    - Create a Spock node named `edge{{ zone }}` for each database.
    - Store the connection DSN for other nodes to subscribe.
    - DSN format: `host={{ inventory_hostname }} user={{ pgedge_user }}
      dbname={{ db_name }} port={{ pg_port }}`.

2. Create Spock subscriptions.
    - Create subscriptions from the current node to all remote nodes.
    - Subscription name format: `sub_n{{ zone }}_n{{ remote_zone }}`.
    - Connect directly to remote Postgres instances.
    - Exclude the current node to prevent self-subscription.

The result is a full mesh topology where all nodes replicate to all other
nodes.

!!! important "Full Mesh Topology"
    This role creates a full mesh topology where every node replicates to
    every other node; this provides maximum availability but increases
    network traffic and complexity.

### HA Deployment

When `is_ha_cluster` is `true`, the role creates zone-based connections
through HAProxy:

1. Verify proxy connectivity.
    - Test connectivity to all HAProxy instances.
    - Verify `pgedge_user` can authenticate through the proxy.
    - Retry up to 5 times with 10-second delays.

2. Create Spock nodes.
    - Create a Spock node named `edge{{ zone }}` for each database.
    - DSN points to HAProxy rather than direct nodes.
    - DSN format: `host={{ subscribe_target }} user={{ pgedge_user }}
      dbname={{ db_name }} port={{ proxy_port }}`.

3. Create Spock subscriptions.
    - Create subscriptions to each remote zone.
    - Subscription name format: `sub_n{{ zone }}_n{{ remote_zone }}`.
    - Determine connection target in priority order: `proxy_node` variable,
      first HAProxy node in remote zone, or first pgedge node as fallback.

The result is a zone-to-zone topology through HAProxy for failover protection.

!!! info "Zone-Based Replication"
    In HA mode, replication is zone-based through HAProxy; this provides
    failover protection and simplifies the topology, but requires HAProxy
    to be properly configured.

### Subscription Synchronization

After creating subscriptions, the role waits for synchronization:

1. Wait for initial sync.
    - Use the `spock.sub_wait_for_sync()` function.
    - Ensure data consistency before completing.
    - Block until all subscriptions are ready.

!!! warning "Initial Sync"
    The role waits for subscriptions to complete initial synchronization;
    for large databases, this can take considerable time, so ensure
    sufficient network bandwidth and disk I/O.

!!! warning "Subscription Names"
    Subscription names follow the format `sub_n{{ zone }}_n{{ remote_zone }}`;
    changing zone assignments after initial setup can cause subscription
    conflicts or render the cluster inoperable.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Standalone Multi-Master Cluster

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

This creates full mesh replication between all nodes for both databases.

### HA Multi-Master with HAProxy

In the following example, the playbook deploys an HA multi-master cluster
with HAProxy for failover:

```yaml
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy

- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
  roles:
    - setup_patroni
    - setup_pgedge
```

This creates zone-based replication through HAProxy.

### Custom Proxy Configuration

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

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `~postgres/.pgpass` | Modified | Password file entry for pgedge user authentication. |

The role also creates database objects in each configured database:

| Object | Location | Purpose |
|--------|----------|---------|
| Spock nodes | `spock.node` table | Node metadata with `node_id` and `node_name`. |
| Spock subscriptions | `spock.subscription` table | Subscription metadata with `sub_id` and `sub_name`. |
| Replication slots | System catalog | Logical replication slots for each subscription. |

## Platform-Specific Behavior

This role behaves identically on all supported platforms including Debian 12
and Rocky Linux 9.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Check if Spock nodes exist before creation.
- Check if subscriptions exist before creation.

The role may update these items on subsequent runs:

- Modify specific lines in the `.pgpass` file.

!!! warning "Subscription Changes"
    Adding new nodes or databases requires re-running this role on all nodes
    to establish new subscriptions.
