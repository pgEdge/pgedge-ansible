# role_config

The `role_config` role provides the foundational configuration for the pgEdge
Ansible Collection. It defines shared variables and computed values that all
other roles use for consistent behavior across the collection.

Do not call this role directly in your playbooks. Other roles include
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
values to other roles. Set the parameters in the inventory file as shown in
the following example:

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

See the [Configuration Reference](../configuration.md) for a complete list
of available parameters.

## How It Works

This role processes configuration and provides computed values to other roles.

### Variable Validation

This role validates several configuration values to ensure correctness. The
`exception_behaviour` parameter must be one of the following values:

- `discard` discards the failing transaction and continues.
- `transdiscard` discards the entire transaction on any error.
- `sub_disable` disables the subscription on conflict.

The `backup_repo_type` parameter must be one of the following values:

- `ssh` uses SSH-based backup repository access.
- `s3` uses S3-compatible object storage for backups.

### Computed Variables

This role computes several variables for use in other roles. Node filtering
variables include the following computed values:

- `nodes_in_zone` contains hosts in the `pgedge` group of the current zone.
- `proxies_in_zone` contains hosts in the `haproxy` group of the current zone.
- `backups_in_zone` contains hosts in the `backup` group of the current zone.
- `first_node_in_zone` contains the first pgedge node in the current zone.

OS-specific shortcut variables include the following computed values:

- `pg_service_name` contains the OS-specific Postgres service name.
- `pg_config_dir` contains the OS-specific configuration directory path.

The `default_patroni_dcs_params` variable contains the etcd connection
settings that `setup_patroni` applies when the inventory does not supply its
own `patroni_dcs.parameters` value.

### Postgres Feature Checks

The `pg_version` parameter pins a Postgres major version, but some
configuration parameters exist only in certain releases, and Postgres refuses
to start when its configuration names a parameter it does not recognize. The
role provides a `pg_feature_checks` task file that asks the installed Postgres
binary which parameters it recognizes and records the answers as facts:

- `pg_supports_output_plugin_libraries` reports whether the installed release
  recognizes `output_plugin_libraries`.

Asking the binary rather than comparing release numbers keeps the checks
correct when a fix reaches an unexpected release, as happens with backports to
older branches and with pgEdge's own patched builds.

Unlike the rest of this role, that task file does not run automatically as a
dependency, because it requires Postgres to be installed. Roles that need the
values include it explicitly:

```yaml
- name: Determine which configuration parameters Postgres recognizes
  include_role:
    name: role_config
    tasks_from: pg_feature_checks
```

The `setup_postgres` and `setup_patroni` roles both include it. The task file
skips each check that already holds a value, so repeated inclusion costs
nothing and an inventory may set a check directly when the binary is
unreachable.

### Platform-Specific Values

The `pg_service_name` variable contains the appropriate service name for the
operating system. The following table shows the values by OS family:

| OS Family | Service Name |
|-----------|--------------|
| RHEL | `postgresql-{{ pg_version }}` (e.g., `postgresql-17`) |
| Debian | `postgresql@{{ pg_version }}-main` (e.g., `postgresql@17-main`) |

The `pg_config_dir` variable contains the configuration file directory. The
following table shows the values by OS family:

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
