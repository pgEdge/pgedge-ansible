# Postgres Configuration

Parameters in this category include any settings that affect how the Postgres
service operates. This can include software versions, installation directories,
listening ports, and similar settings.

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

In the following example, the inventory specifies the default Postgres port:

```yaml
pg_port: 5432
```

## pg_home

- Type: String
- Default: OS-dependent
- Description: This parameter specifies the home directory of the `postgres`
  OS user. The value primarily determines defaults for other dependent
  variables.

    - For RHEL-family systems, the default is `/var/lib/pgsql`.
    - For Debian-family systems, the default is `/var/lib/postgresql`.

In the following example, the inventory specifies a custom home directory:

```yaml
pg_home: /home/postgres
```

## pg_path

- Type: String
- Default: OS-dependent

    - For RHEL-family systems, the default is `/usr/pgsql-{{ pg_version }}`.
    - For Debian-family systems, the default is
      `/usr/lib/postgresql/{{ pg_version }}`.

- Description: This parameter specifies the directory containing Postgres
  binaries and libraries. You can specify this parameter for custom
  installations.

In the following example, the inventory specifies a custom binary path:

```yaml
pg_path: /opt/postgresql/17
```

## pg_data

- Type: String
- Default: OS-dependent

    - For RHEL-family systems, the default is
      `{{ pg_home }}/{{ pg_version }}/data`.
    - For Debian-family systems, the default is
      `{{ pg_home }}/{{ pg_version }}/main`.

- Description: This parameter specifies the Postgres data directory. You can
  specify this parameter for custom locations.

In the following example, the inventory specifies a custom data directory:

```yaml
pg_data: /data/postgresql
```

## custom_hba_rules

- Type: List of dictionaries
- Default: `[]`
- Description: This parameter provides a list of user-specified rules for the
  `pg_hba.conf` file. The collection recognizes the following fields:

    - The `contype` field specifies the connection type such as `local`,
      `host`, or `hostssl`; the default is `host`.
    - The `users` field specifies a comma-separated list of database users;
      the default is `postgres`.
    - The `databases` field specifies a comma-separated list of databases;
      the default is `postgres`.
    - The `method` field specifies the authentication method; the default
      is `scram-sha-256`.
    - The `source` field specifies the IP and mask or hostname of allowed
      connections; the default is `127.0.0.1/32`.

- Since: 1.0.0

In the following example, the inventory adds a custom HBA rule for SSL
connections:

```yaml
custom_hba_rules:
  - contype: hostssl
    users: analyst
    databases: reporting
    source: 10.0.0.0/8
```
