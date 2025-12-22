# Inventory Structure

## Basic Inventory Format

You typically write inventories in YAML format:

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

The collection recognizes the following inventory groups:

### pgedge (Required)

This group contains PostgreSQL nodes that participate in distributed replication.

```yaml
pgedge:
  hosts:
    pg-node1.example.com:
      zone: 1
    pg-node2.example.com:
      zone: 2
```

### haproxy (Optional - HA Only)

This group contains load balancer nodes for high-availability clusters. The group is only relevant when you enable the `is_ha_cluster` parameter.

```yaml
haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
    proxy2.example.com:
      zone: 2
```

### backup (Optional)

This group contains dedicated backup servers when using SSH backup mode.

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
