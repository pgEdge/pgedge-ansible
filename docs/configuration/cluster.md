# Cluster Configuration

The collection uses cluster-wide configuration variables across multiple roles.

## Basic Operation

### db_names

- Type: List
- Default: `[ demo ]`
- Description: Database names for the Spock cluster. At least one database is required. The roles create any missing databases automatically.

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
- Description: Canonical name for the cluster. The collection uses this name for descriptive items and generated values.

```yaml
cluster_name: production-cluster
```

### zone

- Type: Integer
- Default: `1`
- Description: Zone or region identifier for a node. This parameter serves the following purposes:

    - Organizes nodes into logical groups
    - Determines HA cluster boundaries
    - Used as the snowflake sequence ID

!!! important
    In simple clusters, use one node per zone. In HA clusters, assign multiple nodes to the same zone.

```yaml
hosts:
  node1.example.com:
    zone: 1
  node2.example.com:
    zone: 2
```

## Cluster Users

The cluster requires several user roles for proper operation. The collection creates and maintains these roles automatically.

!!! warning "Security"
    Never commit passwords to version control. Use Ansible Vault or environment variables for any of the `_password` parameters when possible.

### db_user

- Type: String
- Default: `admin`
- Description: Primary database username. This username must differ from the OS user running Ansible.

```yaml
db_user: appuser
```

### db_password

- Type: String
- Default: `secret`
- Description: Password for the database user.

```yaml
db_password: "{{ vault_db_password }}"
```

### pgedge_user

- Type: String
- Default: `pgedge`
- Description: Database username for pgEdge inter-node logical replication.

```yaml
pgedge_user: pgedge
```

### pgedge_password

- Type: String
- Default: `secret`
- Description: Password for the pgEdge replication user.

```yaml
pgedge_password: "{{ vault_pgedge_password }}"
```

### replication_user

- Type: String
- Default: `replicator`
- Description: Username for Patroni streaming replication (HA clusters only).

```yaml
replication_user: replicator
```

### replication_password

- Type: String
- Default: `secret`
- Description: Password for the Patroni replication user.

```yaml
replication_password: "{{ vault_replication_password }}"
```

## High Availability

The following settings control how high availability functions within the cluster or per zone.

### is_ha_cluster

- Type: Boolean
- Default: `false`
- Description: This parameter enables high availability features including etcd, Patroni, and HAProxy.

```yaml
is_ha_cluster: true
```

### synchronous_mode

- Type: Boolean
- Default: `false`
- Description: This parameter enables Patroni management of `synchronous_commit` and `synchronous_standby_names` based on cluster state.

```yaml
synchronous_mode: true
```

### synchronous_mode_strict

- Type: Boolean
- Default: `false`
- Description: This parameter enforces synchronous commit when you enable synchronous mode, even if no synchronous replicas are available. This setting can prevent writes during replica failures.

```yaml
synchronous_mode_strict: false
```

!!! warning "Data Availability Trade-off"
    Strict synchronous mode prioritizes data durability over availability. Writes will be blocked if synchronous replicas are unavailable.


