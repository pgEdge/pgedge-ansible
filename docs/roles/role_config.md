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
- `pg_calculated_parameters` maps each calculated Postgres parameter to the
  formula's value, which `init_server` compares `pg_parameters` against.
- `pg_sized_parameters` maps each calculated Postgres parameter to the larger
  of the formula's value and the [sizing floor](#sizing-floor).
  `pg_default_parameters` includes it.
- `pg_undersized_parameters` lists each calculated parameter `pg_parameters`
  sets below the formula's value, which `init_server` refuses.

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

### Zone Primary

Anything that writes to a zone has to run on the node running its primary,
because a replica is read-only. On a non-HA cluster that is the zone's only
node. On an HA cluster it is wherever Patroni last put the leader, which after
a failover or switchover is not the zone's first node. The role provides a
`zone_primary` task file that finds that node and records its inventory name
as the `zone_primary` fact on every node of the zone:

```yaml
- name: Find the node that runs this zone's primary
  include_role:
    name: role_config
    tasks_from: zone_primary

- name: Write something to the zone
  ...
  when: inventory_hostname == zone_primary
```

On an HA cluster, every node whose Patroni service is running asks
`patronictl list` for the zone's leader, and the answers are pooled, so a node
new to the zone still finds the leader. Only a zone that has never been
built, where no node has a Patroni configuration file yet, takes its first node
as the primary. A built zone whose Patroni is stopped on every node is not
assumed to be led by its first node, which after a failover may be a standby:
the task file starts Patroni on each member that has a configuration file and a
data directory, stopping any Postgres running outside Patroni first, and lets
the members elect a leader. If no member can start Patroni in a built zone,
the task stops the run. Once Patroni runs, the task file waits briefly for an 
election to settle, then stops unless
Patroni reports exactly one leader among the zone's nodes, and unless every
node reports the same one. Nodes that disagree mean a switchover or failover
is under way outside the run, and the collection does not manage a zone while
something else is changing it.

The task file also stops the run when the zone's primary is not one of the
play's hosts, whether `--limit` left it out or it failed earlier in the run.
Every write to the zone runs there, so a run without it would skip them.

The `setup_postgres`, `setup_pgedge` and `finalize_backrest` roles include
it.

### Sizing Floor

The worker and slot formulas count the zones and the databases in `db_names`,
so their values go down when either does. Postgres refuses to start when it
finds more replication slots on disk than `max_replication_slots` allows, and
Spock cannot start the workers it needs in a smaller pool, so a database whose
name is removed before it is retired would leave a restarted node in one state
or the other.

The role provides a `sizing_floor` task file that reads back the values the
zone was last configured with and records them as the `pg_sizing_floor` fact,
which maps each calculated parameter to its value. It reads the file the
collection last wrote: `patroni.yml` on an Ultra-HA node, whose bootstrap
section carries the same parameters `setup_patroni` writes into the zone's
store, and `postgresql.conf` otherwise. Every node of the zone in the play is
read and the largest value kept. A file answers whether or not Postgres or
Patroni is running, and a zone that has not been built has no file and no
floor.

`pg_sized_parameters` takes the larger of each formula's value and the floor,
so the calculated values go up with the cluster and never come down on their
own. A value in `pg_parameters` replaces both, which is how an operator lowers
a pool, and `init_server` measures it against the formula alone.

`setup_postgres` includes it before writing `postgresql.conf` on a simple
cluster, and `setup_patroni` includes it before writing `patroni.yml` and the
zone's store.

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

The AI DBA Workbench, a separate monitoring product, is out of scope for
now; its settings will land here alongside its own roles.

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
