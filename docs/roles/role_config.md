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
- `zone_list` contains every zone that holds a pgedge node.

Postgres sizing variables include the following computed values, which follow
the formulas in
[Worker and Replication Sizing](../configuration/postgres.md#worker-and-replication-sizing):

- `pg_spock_nodes`, `pg_connectable_dbs`, `pg_spock_subscriptions`,
  `pg_physical_standbys` and `pg_parallel_workers` contain the formulas'
  inputs.
- `pg_worker_processes` and `pg_replication_slots` contain the calculated
  totals.
- `pg_sized_parameters` maps each calculated Postgres parameter to its value.
  `pg_default_parameters` includes it, and `init_server` compares
  `pg_parameters` against it.

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

### ColdFront and Lakekeeper Settings

ColdFront's settings are defined here because `setup_postgres` writes them
into the Postgres configuration, and because ColdFront shares several of
them with Lakekeeper, its Iceberg catalog:

- `coldfront_enabled` adds ColdFront to the pgEdge nodes. Where it is set,
  `pg_coldfront_parameters` holds the settings ColdFront depends on, which
  join `pg_required_parameters`; `pg_coldfront_default_parameters` holds
  its tuning settings, which join `pg_default_parameters`, so
  `pg_parameters` may override them; and `pg_coldfront_preload_libraries`
  adds `pg_duckdb` and `coldfront` to `pg_preload_libraries`.
- `coldfront_duckdb_role`, `coldfront_db`, and `coldfront_mesh` name the
  role DuckDB execution is gated on and ColdFront's database, and choose
  whether nodes coordinate their cold-tier commits. Each appears in one of
  ColdFront's settings.
- `coldfront_supported_pg_versions` lists the Postgres releases ColdFront
  packages are published for, which `init_server` checks `pg_version`
  against.
- `lakekeeper_host`, `lakekeeper_port`, and `lakekeeper_warehouse` locate the
  Iceberg REST catalog and name the warehouse ColdFront writes through.
- `lakekeeper_metrics_port` sets the port Lakekeeper serves Prometheus
  metrics on. It lives here rather than in either Lakekeeper role because
  `init_server` checks it for collisions and `setup_lakekeeper`
  writes it into the service environment.
- `coldfront_s3_endpoint`, `coldfront_s3_region`, `coldfront_s3_bucket`,
  `coldfront_s3_access_key`, `coldfront_s3_secret_key`, and
  `coldfront_s3_path_style` locate and authenticate to the S3-compatible
  object store behind the cold tier. This is deliberately generic: real AWS
  S3, MinIO, and a self-hosted store are all equally valid backends, and
  this collection deploys none of them. `coldfront_s3_endpoint` stays empty
  to use AWS's own endpoint resolution; set it to point at another store
  instead.

### AI DBA Workbench Settings

The pgEdge AI DBA Workbench's settings are defined here where more than one
role reads them, or where `init_server` checks them; the rest are
`setup_ai_dba_workbench`'s own defaults:

- `ai_dba_workbench_monitor_user` and `ai_dba_workbench_monitor_password` name
  the role the Workbench logs in to every pgEdge node as.
  `setup_ai_dba_workbench_monitor` creates the role on the nodes, the nodes
  admit the Workbench host as it, and `setup_ai_dba_workbench` registers each
  node with it.
- `ai_dba_workbench_db_password` and `ai_dba_workbench_admin_password` are the
  passwords of the Workbench's datastore role and of its administrator. They
  live here so that `init_server` can refuse the defaults, and check the
  administrator's password against the Workbench's own length limits.
- `ai_dba_workbench_port` and `ai_dba_workbench_server_port` set the ports
  nginx and the Workbench server listen on, which `init_server` checks for
  collisions with each other and with `pg_port`.
- `ai_dba_workbench_tls_cert_source` and `ai_dba_workbench_tls_key_source` name
  the web client's certificate and key on the controller, which `init_server`
  requires as a pair.
- `ai_dba_workbench_llm_provider`, `ai_dba_workbench_llm_model`,
  `ai_dba_workbench_llm_api_key`, and `ai_dba_workbench_llm_base_url` choose
  the language model, and the matching `ai_dba_workbench_embedding_*` settings
  the embedding model, which `init_server` checks are complete.
  `ai_dba_workbench_embedding_api_key` and
  `ai_dba_workbench_embedding_base_url` default to the language model's own
  where both name the same provider.

The computed `ai_dba_workbench_enabled` says whether the inventory has a host
in the `ai_dba_workbench` group. It is read from the group itself, so every
host answers it the same way. Where it is true,
`pg_ai_dba_workbench_hba_rules` holds the rule that admits the Workbench host,
as `ai_dba_workbench_monitor_user` and to every database, which joins
`pg_required_hba_rules`: the client authentication rules the collection
depends on beyond the cluster's own hosts, which `setup_postgres` writes into
`pg_hba.conf` on a simple cluster and `setup_patroni` writes into Patroni's
configuration in an HA zone. Each rule names the hosts it admits, which its
writer resolves to their addresses. `init_server` checks the monitoring
password on the pgEdge nodes only where `ai_dba_workbench_enabled` is true,
and `setup_ai_dba_workbench_monitor` stops where it is false.

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
