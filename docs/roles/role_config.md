# role_config

## Overview

The `role_config` role is the foundational configuration role for the entire pgEdge Ansible Collection. The role defines shared variables and computed values that all other roles use, providing a central location for configuration management. You should not call this role directly; the role only ensures that the collection coordinates variables properly across all other roles.

## Purpose

The role performs the following tasks:

- Defines default values for all configurable parameters.
- Computes derived variables based on user configuration.
- Validates configuration settings.
- Provides OS-specific path mappings.
- Filters and organizes inventory hosts by zone.

## Role Dependencies

- None: This is the base role that all other roles depend on

## When to Use

The `role_config` role is automatically included as a dependency by all other roles. You never need to explicitly call it in your playbooks.

## Computed Variables

This role computes some variables for convenient use in other roles.

### Node Filtering

- `nodes_in_zone` - List of hosts in the `pgedge` group of the current zone
- `proxies_in_zone` - List of hosts in the `haproxy` group of the current zone
- `backups_in_zone` - List of hosts in the `backup` group of the current zone
- `first_node_in_zone` - First pgedge node in the current zone. Assuming this is a new cluster, this would be the effective primary in an HA deployment.

### Validated Settings

- `spock_exception_behaviour` - Validated version of `exception_behaviour`
- `backup_type` - Validated version of `backup_repo_type`

### Shortcuts

- `pg_service_name` - OS-specific PostgreSQL service name
    - `postgresql-{{ pg_version }}` on RHEL-family systems (ex: `postgresql-17`)
    - `postgresql@{{ pg_version }}-main` on Debian-family systems (ex: `postgresql@17-main`)
- `pg_config_dir` - OS-specific directory to find configuration files
    - `/etc/postgresql/{{ pg_version }}/main` on Debian systems (ex: `/etc/postgresql/17/main`)
    - `{{ pg_data }}` on all other systems

## Variable Validation

The role validates several configuration values:

### `exception_behaviour`

Must be one of: `discard`, `transdiscard`, `sub_disable`

### `backup_repo_type`

Must be one of: `ssh`, `s3`

## Example Usage

While you don't typically invoke this role directly, you can override its defaults in your inventory:

```yaml
pgedge:
  vars:
    cluster_name: production
    pg_version: 17
    is_ha_cluster: true
    db_names:
      - app_db
      - reporting_db
    db_password: "{{ vault_db_password }}"
    backup_repo_type: s3
    backup_repo_params:
      region: us-west-2
      bucket: my-backups
```

## Notes

!!! important "Password Security"
    Never commit passwords to version control. Use Ansible Vault or environment variables for sensitive values.

!!! info "Zone-Based Filtering"
    Other roles heavily use the `nodes_in_zone`, `proxies_in_zone`, and `backups_in_zone` variables to determine which hosts to interact with during configuration.
