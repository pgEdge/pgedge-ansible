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
`ssl`, `timezone`, `max_worker_processes`, `max_replication_slots`,
`max_wal_senders`, `hot_standby_feedback` and the Spock conflict and DDL
settings. `pg_default_parameters` in the `role_config` role's variables lists
them all.

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
  maintenance window or with a rolling-restart playbook of your own.

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
