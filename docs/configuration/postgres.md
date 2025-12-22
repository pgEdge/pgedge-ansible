# PostgreSQL Configuration

Parameters in this category include any settings which affect how the Postgres service itself operates. This can include software versions, installation directories, listening ports, and so on.

## pg_version

- Type: Integer
- Default: `17`
- Description: This parameter specifies the PostgreSQL major version to install.

```yaml
pg_version: 17
```

## pg_port

- Type: Integer
- Default: `5432`
- Description: This parameter specifies the port where PostgreSQL listens for connections.

```yaml
pg_port: 5432
```

## pg_home

- Type: String
- Default: OS-dependent
- Description: This parameter specifies the home directory of the `postgres` OS user. The value primarily determines defaults for other variables.

    - RHEL: `/var/lib/pgsql`
    - Debian: `/var/lib/postgresql`

```yaml
pg_home: `/home/postgres`
```

## pg_path

- Type: String
- Default: OS-dependent

    - RHEL: `/usr/pgsql-{{ pg_version }}`
    - Debian: `/usr/lib/postgresql/{{ pg_version }}`

- Description: This parameter specifies the directory containing PostgreSQL binaries and libraries. You can specify this parameter for custom installations.

```yaml
pg_path: /opt/postgresql/17
```

## pg_data

- Type: String
- Default: OS-dependent

    - RHEL: `{{ pg_home }}/{{ pg_version }}/data`
    - Debian: `{{ pg_home }}/{{ pg_version }}/main`

- Description: This parameter specifies the PostgreSQL data directory. You can specify this parameter for custom locations.

```yaml
pg_data: /data/postgresql
```

## custom_hba_rules

- Type: List of dictionaries
- Default: `[]`
- Description: This parameter provides a list of user-specified rules for the `pg_hba.conf` file. The following fields are recognized:

    - `contype` - Type of allowed connection (`local`, `host`, `hostssl`) (default: `host`)
    - `users` - Comma-separated list of database users (default: `postgres`)
    - `databases` - Comma-separated list of databases  (default: `postgres`)
    - `method` - Authentication method to allow (default: `scram-sha-256`)
    - `source` - IP + mask, or hostname of allowed connection (default: `127.0.0.1/32`)

- Since: 1.0.0

```yaml
custom_hba_rules:
  - contype: hostssl
    users: analyst
    databases: reporting
    source: 10.0.0.0/8
```
