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
