# role_config

## Overview

The `role_config` role is the foundational configuration role for the entire pgEdge Ansible Collection. It defines shared variables and computed values used by all other roles, providing a central location for configuration management. It is not intended to be called directly, but only to ensure certain variables are coordinated properly across all other roles.

## Purpose

- Define default values for all configurable parameters
- Compute derived variables based on user configuration
- Validate configuration settings
- Provide OS-specific path mappings
- Filter and organize inventory hosts by zone

## Role Dependencies

- **None** - This is the base role that all other roles depend on

## When to Use

The `role_config` role is automatically included as a dependency by all other roles. You never need to explicitly call it in your playbooks.

## Computed Variables

Some variables are computed for use in other roles for convenience by this role.

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
    The `nodes_in_zone`, `proxies_in_zone`, and `backups_in_zone` variables are heavily used by other roles to determine which hosts to interact with during configuration.

## See Also

- [Configuration Reference](../configuration.md) - Complete variable documentation
