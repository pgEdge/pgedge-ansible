# role_config

The `role_config` role provides the foundational configuration for the pgEdge
Ansible Collection. It defines shared variables and computed values that all
other roles use for consistent behavior across the collection.

You should not call this role directly in your playbooks. Other roles include
`role_config` as a dependency to ensure variable coordination throughout the
deployment process.

This role performs the following tasks:

- Define default values for all configurable parameters.
- Compute derived variables based on user configuration.
- Validate configuration settings for correctness.
- Provide OS-specific path mappings for cross-platform support.
- Filter and organize inventory hosts by zone.

## Role Dependencies

This role has no dependencies and serves as the base for all other roles.

## When to Use

Other roles automatically include `role_config` as a dependency. You never
need to explicitly call the role in your playbooks.

## Configuration

This role reads configuration from the inventory file and provides computed
values to other roles.

Set the parameters in the inventory file as shown in the following example:

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

See the [Configuration section](../configuration/index.md) for a complete
list of available parameters.

## How It Works

This role processes configuration and provides computed values to other roles
in the collection.

### Variable Validation

This role validates several configuration values to ensure correctness.

The `exception_behaviour` parameter must be one of these values:

- `discard` discards the failing transaction and continues.
- `transdiscard` discards the entire transaction on any error.
- `sub_disable` disables the subscription on conflict.

The `backup_repo_type` parameter must be one of these values:

- `ssh` uses SSH-based backup repository access.
- `s3` uses S3-compatible object storage for backups.

### Computed Variables

This role computes several variables for convenient use in other roles.

Node filtering variables include these computed values:

- `nodes_in_zone` contains hosts in the `pgedge` group of the current zone.
- `proxies_in_zone` contains hosts in the `haproxy` group of the current zone.
- `backups_in_zone` contains hosts in the `backup` group of the current zone.
- `first_node_in_zone` contains the first pgedge node in the current zone.

Validated setting variables include these computed values:

- `spock_exception_behaviour` contains the validated `exception_behaviour`.
- `backup_type` contains the validated `backup_repo_type`.

OS-specific shortcut variables include these computed values:

- `pg_service_name` contains the OS-specific Postgres service name.
- `pg_config_dir` contains the OS-specific configuration directory path.

### Platform-Specific Values

The `pg_service_name` variable contains the appropriate service name for
the operating system.

| OS Family | Service Name |
|-----------|--------------|
| RHEL | `postgresql-{{ pg_version }}` (e.g., `postgresql-17`) |
| Debian | `postgresql@{{ pg_version }}-main` (e.g., `postgresql@17-main`) |

The `pg_config_dir` variable contains the configuration file directory.

| OS Family | Configuration Directory |
|-----------|------------------------|
| Debian | `/etc/postgresql/{{ pg_version }}/main` |
| RHEL | `{{ pg_data }}` |

## Usage Examples

While you do not invoke this role directly, you can override its defaults
in your inventory file.

### Basic Configuration

In the following example, the inventory file sets basic cluster parameters:

```yaml
pgedge:
  vars:
    cluster_name: production
    pg_version: 17
    db_names:
      - myapp
```

### High Availability Configuration

In the following example, the inventory file enables high availability mode:

```yaml
pgedge:
  vars:
    cluster_name: production
    pg_version: 17
    is_ha_cluster: true
    synchronous_mode: true
```

### Backup Configuration

In the following example, the inventory file configures S3 backups:

```yaml
pgedge:
  vars:
    backup_repo_type: s3
    backup_repo_params:
      region: us-west-2
      bucket: my-backups
      endpoint: s3.amazonaws.com
```

!!! important "Password Security"
    Never commit passwords to version control. Use Ansible Vault or
    environment variables for sensitive values.

!!! info "Zone-Based Filtering"
    Other roles use the `nodes_in_zone`, `proxies_in_zone`, and
    `backups_in_zone` variables to determine which hosts to interact with
    during configuration.
