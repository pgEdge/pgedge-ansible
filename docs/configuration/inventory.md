# Inventory Structure

The inventory file defines the hosts and groups that participate in your
pgEdge cluster deployment. This page describes the inventory format and the
host groups that the collection recognizes.

## Basic Inventory Format

Write inventories in YAML format. The following example shows the basic
structure:

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

## Variable Precedence

You can set variables at multiple levels. The following list shows precedence
from highest to lowest:

1. Host variables in inventory files take first precedence.
2. Group variables in inventory files take second precedence.
3. Variables in the `group_vars/` directory take third precedence.
4. Variables in the `host_vars/` directory take fourth precedence.
5. Role default settings provide fallback values.

The following example shows how host variables override group variables:

```yaml
pgedge:
  vars:
    cluster_name: production
    db_password: group_password
  hosts:
    node1.example.com:
      # Overrides group variable for this host only
      db_password: node1_password
      zone: 1
```

## Using Ansible Vault

Use Ansible Vault to protect sensitive variables. The following command
creates an encrypted variable file:

```bash
ansible-vault create group_vars/pgedge/vault.yml
```

Place sensitive values in the vault file:

```yaml
vault_db_password: secure_password_123
vault_pgedge_password: replication_password_456
vault_backup_cipher: encryption_key_789
```

Reference vault variables in the inventory:

```yaml
pgedge:
  vars:
    db_password: "{{ vault_db_password }}"
    pgedge_password: "{{ vault_pgedge_password }}"
```

Run playbooks with the vault password:

```bash
ansible-playbook -i inventory.yaml playbook.yaml --ask-vault-pass
```

## Host Groups

The collection recognizes the following inventory groups.

### pgedge (Required)

This group contains Postgres nodes that participate in distributed replication.
The `zone` variable must be unique per node in simple clusters and shared among
nodes in the same Patroni cluster in HA clusters.

```yaml
pgedge:
  hosts:
    pg-node1.example.com:
      zone: 1
    pg-node2.example.com:
      zone: 2
```

### haproxy (Optional - HA Only)

This group contains load balancer nodes for high-availability clusters. The
group is only relevant when you enable the `is_ha_cluster` parameter.

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
Define this group when you set `backup_repo_type` to `ssh`.

```yaml
backup:
  hosts:
    backup1.example.com:
      zone: 1
    backup2.example.com:
      zone: 2
```

## Complete Inventory Example

The following example shows a complete inventory for an Ultra-HA cluster with
dedicated backup servers in two zones:

```yaml
all:
  vars:
    ansible_user: pgedge

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
