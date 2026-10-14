# Postgres Configuration

These parameters control how the Postgres service operates, including software
versions, installation directories, and listening ports.

## pg_version

- Type: Integer
- Default: `17`
- Description: This parameter specifies the Postgres major version to install.

In the following example, the inventory specifies Postgres version 17:

```yaml
pg_version: 17
```

## pg_port

- Type: Integer
- Default: `5432`
- Description: This parameter specifies the port where Postgres listens for
  connections.

In the following example, the inventory specifies a non-standard Postgres port:

```yaml
pg_port: 5433
```

## pg_home

- Type: String
- Default: OS-dependent
- Description: This parameter specifies the home directory of the `postgres`
  OS user. The value primarily determines defaults for other path variables.
  Override this parameter only when your system uses a non-standard location.

  - For RHEL-family systems, the default is `/var/lib/pgsql`.
  - For Debian-family systems, the default is `/var/lib/postgresql`.

In the following example, the inventory specifies a custom home directory:

```yaml
pg_home: /home/postgres
```

## pg_path

- Type: String
- Default: OS-dependent
- Description: This parameter specifies the directory containing Postgres
  binaries and libraries. Override this parameter only for custom
  installations.

  - For RHEL-family systems, the default is `/usr/pgsql-{{ pg_version }}`.
  - For Debian-family systems, the default is
    `/usr/lib/postgresql/{{ pg_version }}`.

In the following example, the inventory specifies a custom binary path:

```yaml
pg_path: /opt/postgresql/17
```

## pg_data

- Type: String
- Default: OS-dependent
- Description: This parameter specifies the Postgres data directory. Override
  this parameter only for custom installation locations.

  - For RHEL-family systems, the default is
    `{{ pg_home }}/{{ pg_version }}/data`.
  - For Debian-family systems, the default is
    `{{ pg_home }}/{{ pg_version }}/main`.

In the following example, the inventory specifies a custom data directory:

```yaml
pg_data: /data/postgresql
```

## custom_hba_rules

- Type: List of dictionaries
- Default: `[]`
- Description: This parameter provides a list of additional rules to append
  to the default `pg_hba.conf` rule set. The default rules use a
  least-privilege model and only include entries for known users and database
  combinations. Each rule dictionary accepts the following fields:

  - `contype` specifies the connection type such as `local`, `host`, or
    `hostssl`; the default is `host`.
  - `users` specifies a comma-separated list of database users; the default
    is `postgres`.
  - `databases` specifies a comma-separated list of databases; the default
    is `postgres`.
  - `method` specifies the authentication method; the default is
    `scram-sha-256`.
  - `source` specifies the IP address and mask or hostname of allowed
    connections; the default is `127.0.0.1/32`.

In the following example, the inventory adds a custom HBA rule for SSL
connections from a specific network:

```yaml
custom_hba_rules:
  - contype: hostssl
    users: analyst
    databases: reporting
    source: 10.0.0.0/8
```

## pg_parameters

- Type: Dictionary
- Default: `{}`
- Description: This parameter sets Postgres configuration parameters, by name.
  The collection applies the values on top of its own defaults, so you only
  need to name the parameters you want to change. The parameters work the same
  way on a simple cluster and on an Ultra-HA cluster.

  - Names are matched without regard to case, as Postgres matches them, so
    `TimeZone` overrides the collection's default `timezone`.
  - YAML booleans become `on` and `off`. Numbers are written as numbers, and
    every other value as a quoted string, so `work_mem: 64MB` works as
    written.
  - A `null` value removes a collection default, and Postgres then uses its
    built-in value.
  - `shared_preload_libraries` accepts a list or a comma-separated string, and
    its libraries are **added** to the ones the collection loads. `spock` and
    `snowflake` always load first, followed by `pg_stat_statements`. Setting
    `shared_preload_libraries` to `null` drops `pg_stat_statements` but never
    `spock` or `snowflake`.
  - Removing a parameter from `pg_parameters` removes it from the cluster at the
    next run.

In the following example, the inventory tunes memory, logs slow statements,
and loads `auto_explain` beside the collection's libraries:

```yaml
pg_parameters:
  work_mem: 64MB
  maintenance_work_mem: 1GB
  log_min_duration_statement: 1000
  jit: off
  shared_preload_libraries: auto_explain
```

### Parameters the Collection Controls

Spock needs some parameters set to particular values, and some parameters
follow other settings in the inventory or are set by Patroni. `init_server`
rejects an inventory that sets any of them in `pg_parameters`, and the error
names the setting to change instead.

| Parameter | Controlled by |
|-----------|---------------|
| `port` | `pg_port` |
| `listen_addresses` | The collection; Postgres listens on every address. |
| `ssl_cert_file`, `ssl_key_file` | The collection, which issues the certificate. |
| `wal_level`, `track_commit_timestamp` | The collection; Spock requires `logical` and `on`. |
| `archive_mode`, `archive_command`, `restore_command` | The backup settings, as described in [Backup Configuration](backup.md). |
| `snowflake.node` | `zone` |
| `spock.exception_behaviour` | `exception_behaviour` |
| `output_plugin_libraries` | The collection, on Postgres releases that support the parameter. |
| `hot_standby`, `cluster_name` | Patroni |
| `data_directory` | `pg_data` |
| `hba_file` | `custom_hba_rules` |
| `config_file`, `ident_file`, `unix_socket_directories` | The collection. |

The collection's other defaults can be overridden. These defaults include
`ssl`, `timezone`, `hot_standby_feedback` and the Spock conflict and DDL
settings. `pg_default_parameters` in the `role_config` role's variables lists
them all. The defaults for `max_worker_processes`, `max_replication_slots`,
`max_wal_senders` and, on Postgres 18 and later,
`max_active_replication_origins` are calculated from the cluster, as described
in the next section.

### Worker and Replication Sizing

Spock needs background workers, walsenders, replication slots and replication
origins on every node. The number of each grows with the number of zones and
with the number of databases in `db_names`. Postgres sets aside a fixed number
of each when it starts, so a cluster that outgrows them does not slow down. It
stops replicating. Spock cannot start the worker it needs, logs an error, and
retries in a loop, and a subscription never leaves the `initializing` state.

To prevent this, the collection calculates these four parameters from the
inventory instead of using fixed values. The formulas come from the Spock
documentation's sizing guide, which explains each term in detail. They use the
following values:

- `N` is the number of zones. Every zone holds one Spock node, however many
  members it has.
- `D` is the number of databases that accept connections: the databases in
  `db_names`, plus `postgres` and `template1`. Spock starts a manager worker in
  each, whether it replicates or not.
- `S` is the number of subscriptions on each node: the number of databases in
  `db_names` multiplied by `N - 1`.
- `P` is the number of physical standbys in the node's zone: one less than the
  zone's members in an Ultra-HA cluster, and zero otherwise.
- `W` is `max_parallel_workers` from `pg_parameters`, or `8`, its Postgres
  default. Parallel queries draw on the same worker pool as Spock.

The collection calculates the defaults with the following formulas:

    max_worker_processes = 1 + 1 + D + 2 * S + W + 2,  rounded up to a multiple of 4
    max_replication_slots = 2 * S + P + 2,  but no less than 16
    max_wal_senders = max_replication_slots
    max_active_replication_origins = max_replication_slots  (Postgres 18 and later)

The worker formula counts a supervisor, a slot synchronization worker, one
manager for each database, an apply worker and a table synchronization worker
for each subscription, the parallel query workers, and two spare workers. The
slot formula counts an apply slot and a table synchronization slot for each
subscription, a slot for each standby, and two spare slots for tools such as
`pg_basebackup`. Earlier releases set `max_replication_slots` and
`max_wal_senders` to a fixed `16`, and the calculated values never go below it.
If Postgres finds more replication slots on disk than `max_replication_slots`
allows, it refuses to start, so these values must never shrink on an existing
cluster.

The following table shows the calculated values for clusters that replicate a
single database:

| Cluster | `max_worker_processes` | `max_replication_slots`, `max_wal_senders` |
|---------|------------------------|--------------------------------------------|
| 2 zones | 20 | 16 |
| 3 zones | 20 | 16 |
| 4 zones | 24 | 16 |
| 5 zones | 24 | 16 |
| 8 zones | 32 | 16 |

Each additional database raises both values. For example, a 3-zone cluster
that replicates ten databases needs 64 workers and 42 slots.

The calculation changes whenever the cluster does. Adding a zone or a database
to `db_names` raises the values on every node, and the next run applies them.
Every one of these parameters requires a restart, so `pg_allow_restart` decides
whether the run restarts each node or leaves the restart pending.

Removing a zone or a database from `db_names` lowers the values just as
readily, but the collection does not drop the subscriptions and replication
slots the removed zone or database leaves behind. If those slots outnumber the
new `max_replication_slots`, Postgres refuses to start after the next restart.
Before you remove a zone or a database, either drop its subscriptions and slots
on every remaining node, or set the parameters in `pg_parameters` to their
current values until you have.

!!! warning "Overriding the calculated values"

    You can set any of these parameters in `pg_parameters`, and your value
    replaces the calculation completely. The collection does not raise it as the
    cluster grows. If you set one, calculate it yourself with the formulas
    above, and recalculate it whenever you add a zone or a database. The
    formulas cannot account for databases created outside `db_names`, or for
    extensions that start their own background workers, such as `pg_cron`. If
    your nodes have either, add them to the totals yourself.

    `init_server` refuses an inventory where `pg_parameters` sets one of these
    parameters below the calculated value, or sets it to `null`, which falls
    back to Postgres's smaller built-in default. A pool that small eventually
    keeps Spock from starting a worker it needs, and replication stops. Raise
    the value, or remove it from `pg_parameters` to use the calculated one.

### Ultra-HA Clusters

In an Ultra-HA cluster, Patroni keeps each zone's Postgres configuration in its
configuration store, and every member of the zone shares it. This has the
following consequences:

- Every node in a zone must have the same `pg_parameters`. Set the parameter on
  the `pgedge` group, or on a group that holds just the zone's nodes. Different
  zones may use different values. `init_server` rejects a zone whose nodes
  disagree.
- `setup_patroni` updates the store on every run, not only when it bootstraps
  the zone. The collection owns the store's parameters. A parameter that is in
  the store but not in the collection's configuration is removed, so a change
  made by hand with `patronictl edit-config` lasts only until the next run.
- A Debian node's local logging settings (`logging_collector`,
  `log_directory` and `log_filename`) normally take precedence over the store.
  The collection drops each one that `pg_parameters` sets, so your value
  applies.

## pg_allow_restart

- Type: Boolean
- Default: `true`
- Description: This parameter controls whether the collection restarts Postgres
  to apply parameters that only take effect on restart, such as
  `shared_preload_libraries` or `max_worker_processes`. The collection restarts
  only nodes that Postgres or Patroni report as waiting on a restart, and only
  one node at a time. In an Ultra-HA zone it restarts replicas before the
  leader.
  When this parameter is `false`, the run applies everything a reload can apply
  and reports the nodes that still need a restart, so you can restart them in a
  maintenance window or with a rolling-restart playbook of your own. The
  parameter does not apply to a new Ultra-HA zone: the primary is always
  restarted once after Patroni takes it over, because Postgres starts before
  Patroni and only a restart gives it the zone's full configuration.

In the following example, the inventory leaves restarts to the operator:

```yaml
pg_allow_restart: false
```

## Internal Path Variables

The `role_config` role computes the following additional path variables. These
are available for reference when modifying or extending collection roles.

The following table shows the values by OS family:

| Variable | Debian value | RHEL value | Description |
|----------|-------------|------------|-------------|
| pg_config_dir | /etc/postgresql/VERSION/main | pg_data | Path to the PostgreSQL configuration directory. |
| pg_service_name | postgresql@VERSION-main | postgresql-VERSION | Systemd service name for PostgreSQL. |
| patroni_service_name | patroni@VERSION-main | patroni | Systemd service name for Patroni. |
| nodes_in_zone | (computed) | (computed) | List of all pgedge hosts in the same zone as the current node. |
| pg_supports_output_plugin_libraries | (detected) | (detected) | Whether the installed Postgres release recognizes `output_plugin_libraries`. |
