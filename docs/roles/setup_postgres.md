# setup_postgres

## Overview

The `setup_postgres` role initializes and configures Postgres instances for pgEdge deployments. It handles both standalone and high availability configurations, managing database initialization, SSL certificates, user creation, and extension installation.

## Purpose

The role performs the following tasks:

- initializes the Postgres data directory if necessary.
- generates SSL certificates for encrypted connections.
- configures Postgres for logical replication and Spock.
- sets up `pg_hba.conf` for authentication.
- creates database users (admin, replication, pgedge).
- creates and configures databases.
- installs Spock and Snowflake extensions.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `install_pgedge`: You must install pgEdge packages including Postgres

## When to Use

Execute this role on **all pgedge hosts** after installing Postgres:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
```

## Parameters

This role uses the following configuration parameters:

### Database Configuration

- `pg_data`
- `pg_port`
- `pg_version`
- `db_names`
- `db_user`
- `db_password`
- `custom_hba_rules`

### Replication Users

- `pgedge_user`
- `pgedge_password`
- `replication_user`
- `replication_password`

### Extension Configuration

- `spock_exception_behaviour`
- `zone`

### High Availability

- `is_ha_cluster`

## Tasks Performed

### Standalone Postgres Setup

When `is_ha_cluster: false`:

#### 1. Instance Initialization

- **RHEL Systems**: Runs `postgresql-{{ pg_version }}-setup initdb` to create data directory
- **Debian Systems**: Uses auto-initialized cluster from package installation

#### 2. SSL Certificate Generation

The role performs the following SSL certificate tasks:

- generates a self-signed SSL certificate and private key.
- stores files in `{{ pg_data }}/server.crt` and `{{ pg_data }}/server.key`.
- sets secure permissions (600 on key, 644 on certificate).
- configures Postgres to use SSL certificates.

#### 3. Postgres Configuration

The role configures Postgres with the following settings:

* sets the port to `pg_port`.
* will listen to all available IPV4 addresses.
* enables archive mode for later configuration of archive command.
* increases replication slots and WAL senders to 16.
* enables hot standby feedback to avoid query cancellation on replicas.
* enables commit timestamps for Spock conflict resolution.
* adds spock, snowflake, and `pg_stat_statements` to preload libraries.
* sets Spock conflict resolution to `last_update_wins`.
* enables Spock DDL replication.
* sets the default Spock exception behavior to discard the current transaction.
* configures Spock to automatically add new tables to replication sets.
* sets the Snowflake zone to the current server zone.

!!! note "Shared Preload Libraries"
    The role modifies the `shared_preload_libraries` parameter. If this is a pre-existing instance, you must restart Postgres for changes to this setting to take effect.

#### 4. pg_hba.conf Configuration

The role sets up authentication rules:

- local peer access for the `postgres` user.
- localhost connections via SCRAM-SHA-256.
- network access for `pgedge_user` and `db_user` from all cluster nodes.
- optional custom rules via the `custom_hba_rules` variable.

#### 5. Service Startup

The role performs the following service startup tasks:

- starts the Postgres service.
- enables the service for automatic startup.
- waits for the service to be ready.

#### 6. User Creation

Creates database users:

- **Admin User** (`db_user`): Superuser for cluster management
- **pgEdge User** (`pgedge_user`): Superuser with REPLICATION and BYPASSRLS for node communication

#### 7. Database and Extension Setup

The role performs the following database setup tasks:

- creates all databases specified in `db_names`.
- installs the Spock extension in all databases.
- installs the Snowflake extension in all databases.

### High Availability Postgres Setup

When `is_ha_cluster: true`:

Performs all standalone setup tasks plus:

#### 1. Service Management

These steps only occur on the primary node, where the role:

- stops the Postgres service.
- disables automatic startup (Patroni manages the service).
- restarts Postgres temporarily for initial configuration.

!!! note "Postgres Service Management"
    If the Patroni service is running, this role assumes the bootstrapping process has already been executed, and it will not be repeated. This means Postgres will not be stopped.

#### 2. Replication User Configuration

These steps only occur on the primary node:

- Creates replication user (`replication_user`) for Patroni streaming replication
- Adds `pg_hba.conf` rules for `replication_user` from zone nodes
- Configures proxy access for HAProxy health checks
- Creates `.pgpass` entry for automated connections from `replication_user`

#### 3. Replica Node Setup

These steps only occur on replica nodes:

- Stops the Postgres service
- Disables automatic startup (Patroni manages the service)
- **Erases the `pg_data` directory if present** (Patroni will rebuild)

!!! note "Postgres Service Management"
    If the Patroni service is running, this role assumes the bootstrapping process has already been executed, and it will not be repeated. This means Postgres will not be stopped, and the data directory will not be erased.

## Files Generated

### SSL Certificates

- `{{ pg_data }}/server.crt` - SSL certificate (mode 644)
- `{{ pg_data }}/server.key` - SSL private key (mode 600)

### Authentication Files

- `~postgres/.pgpass` - Password file for automated connections

## Files Modified

### Postgres Configuration

- `{{ pg_config_dir }}/postgresql.conf` - Main configuration
- `{{ pg_data }}/pg_hba.conf` - Authentication configuration

## Platform-Specific Behavior

### Debian-Family

- Postgres auto-initializes during package installation
- Data directory: `/var/lib/postgresql/{{ pg_version }}/main`
- Config directory: `/etc/postgresql/{{ pg_version }}/main`
- Service name: `postgresql@{{ pg_version }}-main`
- No manual initdb required

### RHEL-Family

- Requires manual initialization via `postgresql-{{ pg_version }}-setup initdb`
- Data directory: `/var/lib/pgsql/{{ pg_version }}/data`
- Config directory: `/var/lib/pgsql/{{ pg_version }}/data`
- Service name: `postgresql-{{ pg_version }}`

## Example Usage

### Standalone Postgres

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    db_names:
      - production
      - reporting
    db_user: dbadmin
    db_password: "{{ vault_db_password }}"
  roles:
    - install_pgedge
    - setup_postgres
```

### High Availability Cluster

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    db_names: production
  roles:
    - install_repos
    - install_pgedge
    - install_etcd
    - install_patroni
    - setup_postgres
    - setup_etcd
    - setup_patroni
```

### Custom pg_hba.conf Rules

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    custom_hba_rules:
      - contype: host
        users: analyst
        databases: reporting
        source: 10.0.0.0/8
      - contype: hostssl
        users: external_app
        databases: production
        source: 0.0.0.0/0
  roles:
    - setup_postgres
```

### Multiple Databases with Extensions

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    db_names:
      - app_db
      - analytics_db
      - test_db
  roles:
    - setup_postgres
```

## Idempotency

This role is idempotent and safe to re-run.

- The Postgres data directory is only initialized if it is missing.
- Existing SSL certificates are not overwritten.
- Users and databases are only created if they do not exist.
- Extensions are only installed if they are absent.

However, re-running may update:

- configuration blocks in `postgresql.conf`.
- `pg_hba.conf` rules.
- user passwords if they are changed.
- state of the Postgres service.

## Notes

!!! tip "Configuration Management"
    Postgres configuration is managed via the Ansible `blockinfile` module. Manual changes outside the managed block are preserved.
