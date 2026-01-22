# Configuration

This page provides a complete reference for configuring your pgEdge cluster
deployment. The reference includes inventory structure and all available
configuration variables.

## Configuration Overview

The pgEdge Ansible Collection provides the following methods for managing
configuration:

- Inventory files define hosts and host groups for the cluster.
- Group variables set values for all hosts in a group.
- Host variables set values for individual hosts only.
- Role defaults provide fallback values defined in each role.

You can set variables at multiple levels; the following list shows precedence
from highest to lowest:

1. Host variables in inventory files take first precedence.
2. Group variables in inventory files take second precedence.
3. Variables in the `group_vars/` directory take third precedence.
4. Variables in the `host_vars/` directory take fourth precedence.
5. Role default settings provide fallback values.

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

- The `exception_behaviour` parameter must be valid per Spock documentation.
- The `backup_repo_type` parameter must be `ssh` or `s3`.

!!! tip "Validation Errors"
    If you encounter variable validation errors, check the role's
    `vars/main.yaml` for specific validation logic.

## Next Steps

- Review [sample playbooks](../usage.md) for complete configuration examples.
- Understand [role-specific parameters](../roles/index.md) for advanced options.
- Learn about [architecture patterns](../architecture.md) to inform your choices.
