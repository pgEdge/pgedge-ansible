# Configuration

This page provides a complete reference for configuring your pgEdge cluster deployment, including inventory structure and all available configuration variables.

## Configuration Overview

The pgEdge Ansible Collection provides the following methods for managing configuration:

- Inventory files: Define your hosts and host groups
- Group variables: Set variables for all hosts in a group
-  Host variables: Set variables for individual hosts
-  Role defaults: Default values defined in each role
1. Inventory files: Define your hosts and host groups
2. Group variables: Set variables for all hosts in a group
3. Host variables: Set variables for individual hosts
4. Role defaults: Default values defined in each role

You can set variables at multiple levels, with the following precedence (highest to lowest):

1. Host variables in inventory
2. Group variables in inventory
3. Variables in `group_vars/` directory
4. Variables in `host_vars/` directory
5. Role defaults

## Variable Precedence Example

You can override variables at different levels:

```yaml
# Inventory file
pgedge:
  vars:
    # Applies to all hosts in pgedge group
    cluster_name: production
    db_password: group_password
  hosts:
    node1.example.com:
      # Overrides group variable for this host only
      db_password: node1_password
      zone: 1
```

## Using Ansible Vault

Protect sensitive variables using Ansible Vault:

```bash
# Create encrypted variable file
ansible-vault create group_vars/pgedge/vault.yml
```

In the vault file:

```yaml
vault_db_password: secure_password_123
vault_pgedge_password: replication_password_456
vault_backup_cipher: encryption_key_789
```

Reference in inventory:

```yaml
pgedge:
  vars:
    db_password: "{{ vault_db_password }}"
    pgedge_password: "{{ vault_pgedge_password }}"
```

Run playbooks with vault password:

```bash
ansible-playbook playbook.yml --ask-vault-pass
```

## Configuration Validation

The collection validates certain variables:

- `exception_behaviour` must be valid per Spock documentation
- `backup_repo_type` must be `ssh` or `s3`

!!! tip "Validation Errors"
    If you encounter variable validation errors, check the role's `vars/main.yaml` for specific validation logic.

## Next Steps

- Review [sample playbooks](usage.md) for complete configuration examples
- Understand [role-specific parameters](roles/index.md) for advanced customization
- Learn about [architecture patterns](architecture.md) to inform your configuration choices
