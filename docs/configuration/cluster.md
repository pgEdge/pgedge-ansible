# Cluster Configuration

The collection uses cluster-wide configuration variables across multiple roles.
These settings define the basic operation and user accounts for the cluster.

## Basic Operation

These parameters are operational in nature, defining how to organize and label 
cluster resources. While they have functional defaults, we strongly recommend
either changing them in most cases, or including them in host inventories
explicitly to prevent mistakes.

### db_names

- Type: List
- Default: `[ demo ]`
- Description: Database names for the Spock cluster. You must specify at least
  one database. The roles create any missing databases automatically.

In the following example, the inventory specifies database names:

```yaml
# Single database
db_names:
  - myapp

# Multiple databases
db_names:
  - app_db
  - reporting_db
```

### cluster_name

- Type: String
- Default: `demo`
- Description: Canonical name for the cluster. The collection uses this name
  for descriptive items and generated values.

In the following example, the inventory specifies a production cluster name:

```yaml
cluster_name: production-cluster
```

### zone

- Type: Integer
- Default: `1`
- Description: Zone or region identifier for a node. This parameter serves the
  following purposes:

    - The zone organizes nodes into logical groups.
    - The zone determines HA cluster boundaries.
    - The zone value serves as the snowflake sequence ID.

!!! important
    In simple clusters, use one node per zone. In HA clusters, assign multiple
    nodes to the same zone. Zone assignment determines the behavior of several
    roles in this collection, so we strongly encourage setting this parameter
    for each individual inventory host to avoid ambiguity.

In the following example, the inventory assigns each node to a separate zone:

```yaml
hosts:
  node1.example.com:
    zone: 1
  node2.example.com:
    zone: 2
```

## Cluster Users

The cluster requires several user roles for proper operation. The collection
creates and maintains these roles automatically.

!!! warning "Security"
    Never commit passwords to version control. Use Ansible Vault or environment
    variables for any of the `_password` parameters when possible.

### db_user

- Type: String
- Default: `admin`
- Description: Primary database username. This username must differ from the
  OS user running Ansible.

In the following example, the inventory specifies a custom database user:

```yaml
db_user: appuser
```

### db_password

- Type: String
- Default: `secret`
- Description: Password for the database user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
db_password: "{{ vault_db_password }}"
```

### pgedge_user

- Type: String
- Default: `pgedge`
- Description: Database username for pgEdge inter-node logical replication.
  The cluster uses this account for Spock operations.

In the following example, the inventory specifies the pgEdge replication user:

```yaml
pgedge_user: pgedge
```

### pgedge_password

- Type: String
- Default: `secret`
- Description: Password for the pgEdge replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
pgedge_password: "{{ vault_pgedge_password }}"
```

### replication_user

- Type: String
- Default: `replicator`
- Description: Username for Patroni streaming replication. This setting only
  applies to HA clusters.

In the following example, the inventory specifies the replication user:

```yaml
replication_user: replicator
```

### replication_password

- Type: String
- Default: `secret`
- Description: Password for the Patroni replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
replication_password: "{{ vault_replication_password }}"
```

## High Availability

The following settings control how high availability functions within the
cluster or per zone.

### is_ha_cluster

- Type: Boolean
- Default: `false`
- Description: This parameter enables high availability features including
  etcd, Patroni, and HAProxy.

In the following example, the inventory enables high availability mode:

```yaml
is_ha_cluster: true
```

### synchronous_mode

- Type: Boolean
- Default: `false`
- Description: This parameter enables Patroni management of
  `synchronous_commit` and `synchronous_standby_names` based on cluster state.

In the following example, the inventory enables synchronous replication:

```yaml
synchronous_mode: true
```

### synchronous_mode_strict

- Type: Boolean
- Default: `false`
- Description: This parameter enforces synchronous commit when you enable
  synchronous mode, even if no synchronous replicas are available. This setting
  can prevent writes during replica failures.

In the following example, the inventory disables strict synchronous mode:

```yaml
synchronous_mode_strict: false
```

!!! warning "Data Availability Trade-off"
    Strict synchronous mode prioritizes data durability over availability.
    The cluster blocks writes if synchronous replicas become unavailable.
