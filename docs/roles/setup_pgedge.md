# setup_pgedge

## Overview

The `setup_pgedge` role configures Spock logical replication to initialize a multi-master PostgreSQL cluster. It establishes Spock nodes and subscriptions between all applicable PostgreSQL instances, enabling bidirectional data synchronization across zones and nodes.

## Purpose

The role performs the following tasks:

- configures password authentication for `pgedge_user`.
- creates Spock node metadata on each instance.
- establishes Spock subscriptions between all nodes or zone leaders.
- configures multi-master logical replication topology.
- supports both direct node-to-node and proxy-based subscriptions.
- verifies subscription synchronization.
- enables distributed PostgreSQL deployment.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `setup_postgres`: You must install and configure PostgreSQL and Spock extension
- `setup_patroni`: For Patroni management used in HA clusters (optional)
- `setup_haproxy`: For HAProxy communication routing in HA clusters (optional)

!!! information "Role Order"
    When deploying an HA cluster, this role **must** be executed after `setup_patroni` and `setup_haproxy`. Patroni determines which cluster node is the primary writable node in a particular zone, and HAProxy ensures this node receives all Spock-related inter-node communication.

## When to Use

Execute this role on **all pgedge hosts** after PostgreSQL setup to establish multi-master replication:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - setup_pgedge
```

For HA clusters:

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

## Parameters

This role uses the following configuration parameters:

### Database Configuration

- `db_names`
- `pg_port`
- `zone`

### Node Communication Users

- `pgedge_user`
- `pgedge_password`

### Proxy Configuration (optional)

- `proxy_node` - If not specified, will use the first listed node in the `haproxy` group
- `proxy_port`

## Tasks Performed

### 1. User Access Configuration

- Creates `.pgpass` entry for `pgedge_user`
- Stored in `~postgres/.pgpass` with mode 600
- Format: `*:*:*:pgedge:password` for all potential hosts, databases, and ports

### 2. Deployment Type Detection

The role follows different workflows based on cluster configuration:

**Standalone Deployment:**

- Direct node-to-node connections
- No HAProxy involvement
- Subscriptions connect directly to other PostgreSQL nodes

**HA Deployment:**

- Proxy-based connections when available
- Verifies HAProxy connectivity before creating subscriptions
- Subscriptions route through HAProxy for high availability
- Supports failover and optional load balancing

**Replica Nodes:**

- Replica nodes are not bootstrapped as they are managed by Patroni
- Spock replication is configured on the primary, replicas inherit via Patroni

### 3. Establish Node Communication

!!! important "Full Mesh Topology"
    This role creates a full mesh topology where every node or zone replicates to every other node or zone. This provides maximum availability but increases network traffic and complexity.

#### Stand-Alone Nodes

**Spock Node Creation:**

For each database in `db_names`:

- Creates Spock node named `edge{{ zone }}`
- Stores connection DSN for other nodes to subscribe
- DSN format: `host={{ inventory_hostname }} user={{ pgedge_user }} dbname={{ db_name }} port={{ pg_port }}`
- Idempotent: Checks if node exists before creating

**Spock Subscription Creation:**

For each remote node and each database:

- Creates subscription from current node to remote node
- Subscription name format: `sub_n{{ zone }}_n{{ remote_zone }}`
- Connects directly to remote PostgreSQL instance
- Bidirectional: All nodes subscribe to all other nodes
- Excludes current node (no self-subscription)

Result: Full mesh topology where all nodes replicate to all other nodes.

!!! warning "Subscription Names"
    Subscription names follow the format `sub_n{{ zone }}_n{{ remote_zone }}`. Changing zone assignments after initial setup can cause subscription conflicts or render the cluster inoperable.

#### Highly-Available Nodes

!!! info "Zone-Based Replication"
    In HA mode, replication is zone-based through HAProxy. This provides failover protection and simplifies the topology, but requires HAProxy to be properly configured.

**Proxy Verification:**

- Tests connectivity to all HAProxy instances
- Verifies `pgedge_user` can authenticate through proxy
- Retries up to 5 times with 10-second delays
- Ensures proxy layer is functional before creating subscriptions

**Spock Node Creation:**

For each database in `db_names`:

- Creates Spock node named `edge{{ zone }}`
- DSN points to HAProxy proxy (not direct node)
- DSN format: `host={{ subscribe_target }} user={{ pgedge_user }} dbname={{ db_name }} port={{ proxy_port }}`
- Enables high availability for incoming subscriptions

**Spock Subscription Creation:**

For each remote zone and each database:

- Creates subscription to remote zone
- Subscription name format: `sub_n{{ zone }}_n{{ remote_zone }}`
- Determines connection target in priority order:
    1. `proxy_node` variable if set for remote zone
    2. First HAProxy node in remote zone
    3. First pgedge node in remote zone (fallback)
- Connects through proxy for HA benefits
- Zone-level subscriptions (one per zone, not per node)

Result: Zone-to-zone topology through HAProxy for failover protection.

!!! warning "Subscription Names"
    Subscription names follow the format `sub_n{{ zone }}_n{{ remote_zone }}`. Changing zone assignments after initial setup can cause subscription conflicts or render the cluster inoperable.

### 4. Subscription Synchronization

- Waits for all subscriptions to complete initial sync
- Uses `spock.sub_wait_for_sync()` function
- Ensures data consistency before completing
- Blocks until all subscriptions are ready

!!! warning "Initial Sync"
    The role waits for subscriptions to complete initial synchronization. For large databases, this can take considerable time. Ensure sufficient network bandwidth and disk I/O. It is best to use this role on an empty cluster to establish initial architecture.

## Files Generated

### Authentication Files

- `~postgres/.pgpass` - Password file for pgedge user (mode 600)

### Database Objects

**Spock Nodes:**

Created in each database in `spock.node` table:

- `node_id` - Unique node identifier
- `node_name` - `edge{{ zone }}` for each Spock node

**Spock Subscriptions:**

Created in each database in `spock.subscription` table:

- `sub_id` - Unique subscription identifier
- `sub_name` - `sub_n{{ zone }}_n{{ remote_zone }}` for active subscriptions

**Spock Replication Slots:**

Created automatically on provider nodes:

- Logical replication slots for each subscription
- Named based on subscription and database
- Track replication position and lag

## Example Usage

### Standalone Multi-Master Cluster

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

Creates full mesh replication between all nodes for both databases.

### HA Multi-Master with HAProxy

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

Creates zone-based replication through HAProxy.

### Custom Proxy Configuration

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

Uses specific proxy for replication connections instead of HAProxy.

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- only modify specific lines in the `.pgpass` file.
- check if spock nodes exist before creation.
- check if subscriptions exist before creation.

!!! warning "Subscription Changes"
    Adding new nodes or databases requires re-running this role on all nodes to establish new subscriptions.

## Notes

You can monitor Spock replication health:

```bash
# Check node status
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.node;"

# Check subscriptions
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.subscription;"

# Check subscription status
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.sub_show_status();"

# Check replication lag
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.lag_tracker;"
```
