# Inventory Structure

## Basic Inventory Format

Inventories are typically written in YAML format:

```yaml
pgedge:
  vars:
    # Group-level variables apply to all hosts in this group
    cluster_name: production
    db_password: secret123
  hosts:
    node1.example.com:
      zone: 1
    node2.example.com:
      zone: 2
    node3.example.com:
      zone: 3
```

## Host Groups

The collection recognizes these inventory groups:

### pgedge (Required)

PostgreSQL nodes that participate in distributed replication.

```yaml
pgedge:
  hosts:
    pg-node1.example.com:
      zone: 1
    pg-node2.example.com:
      zone: 2
```

### haproxy (Optional - HA Only)

Load balancer nodes for high-availability clusters. Only relevant when `is_ha_cluster: true`.

```yaml
haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
    proxy2.example.com:
      zone: 2
```

### backup (Optional)

Dedicated backup servers when using SSH backup mode.

```yaml
backup:
  hosts:
    backup1.example.com:
      zone: 1
    backup2.example.com:
      zone: 2
```

## Complete Inventory Example

```yaml
# Ultra-HA cluster with backups
pgedge:
  vars:
    cluster_name: prod-cluster
    is_ha_cluster: true
    db_password: "{{ vault_db_password }}"
    pgedge_password: "{{ vault_pgedge_password }}"
  hosts:
    pg-node1.example.com:
      zone: 1
    pg-node2.example.com:
      zone: 1
    pg-node3.example.com:
      zone: 1
    pg-node4.example.com:
      zone: 2
    pg-node5.example.com:
      zone: 2
    pg-node6.example.com:
      zone: 2

haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
    proxy2.example.com:
      zone: 2

backup:
  hosts:
    backup1.example.com:
      zone: 1
    backup2.example.com:
      zone: 2
```
