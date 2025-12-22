# setup_postgres

## Overview

The `setup_postgres` role initializes and configures Postgres instances for pgEdge deployments. It handles both standalone and high availability configurations, managing database initialization, SSL certificates, user creation, and extension installation.

## Purpose

This role performs the following tasks:

- Initializes the Postgres data directory if necessary.
- Generates SSL certificates for encrypted connections.
- Configures Postgres for logical replication and Spock.
- Sets up `pg_hba.conf` for authentication.
- Creates database users (admin, replication, pgedge).
- Creates and configures databases.
- Installs Spock and Snowflake extensions.

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

- Generates self-signed SSL certificate and private key
- Stores in `{{ pg_data }}/server.crt` and `{{ pg_data }}/server.key`
- Sets secure permissions (600 on key, 644 on certificate)
- Configures Postgres to use SSL certificates

#### 3. Postgres Configuration

Configures Postgres with the following settings:

* Sets the port to `pg_port`
* Will listen to all available IPV4 addresses
* Enables archive mode for later configuration of archive command
* Increases replication slots and WAL senders to 16
* Enables hot standby feedback to avoid query cancellation on replicas
* Enables commit timestamps for Spock conflict resolution
* Adds spock, snowflake, and `pg_stat_statements` to preload libraries
* Sets Spock conflict resolution to `last_update_wins`
* Enables Spock DDL replication
* Sets the default Spock exception behavior to discard the current transaction
* Configures Spock to automatically add new tables to replication sets
* Sets the Snowflake zone to the current server zone

!!! note "Shared Preload Libraries"
    The role modifies the `shared_preload_libraries` parameter. If this is a pre-existing instance, you must restart Postgres for changes to this setting to take effect.

#### 4. pg_hba.conf Configuration

Sets up authentication rules:

- Local peer access for `postgres` user
- Localhost connections via SCRAM-SHA-256
- Network access for `pgedge_user` and `db_user` from all cluster nodes
- Optional custom rules via `custom_hba_rules` variable

#### 5. Service Startup

- Starts Postgres service
- Enables service for automatic startup
- Waits for service to be ready

#### 6. User Creation

Creates database users:

- **Admin User** (`db_user`): Superuser for cluster management
- **pgEdge User** (`pgedge_user`): Superuser with REPLICATION and BYPASSRLS for node communication

#### 7. Database and Extension Setup

- Creates all databases specified in `db_names`
- Installs Spock extension in all databases
- Installs Snowflake extension in all databases

### High Availability Postgres Setup

When `is_ha_cluster: true`:

Performs all standalone setup tasks plus:

#### 1. Service Management

These steps only occur on the primary node:

- Stops the Postgres service
- Disables automatic startup (Patroni manages the service)
- Restarts Postgres temporarily for initial configuration

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

This role is designed for idempotency:

- The Postgres data directory is only initialized if it is missing.
- Existing SSL certificates are not overwritten.
- Users and databases are only created if they do not exist.
- Extensions are only installed if they are absent.

However, re-running may update:

- Configuration blocks in `postgresql.conf`
- `pg_hba.conf` rules
- User passwords if changed
- Service state

## Troubleshooting

### initdb Fails on RHEL

**Symptom:** `postgresql-{{ pg_version }}-setup initdb` command fails

**Solution:**

- Verify Postgres packages are installed
- Check data directory permissions:

```bash
ls -la /var/lib/pgsql/17
```

- Manually initialize:

```bash
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
```

### SSL Certificate Generation Fails

**Symptom:** Cannot create SSL certificates

**Solution:**

- Verify OpenSSL is installed:

```bash
openssl version
```

- Check data directory permissions
- Manually generate certificates:

```bash
sudo -u postgres openssl req -new -x509 -days 365 -nodes \
  -text -out /var/lib/pgsql/17/data/server.crt \
  -keyout /var/lib/pgsql/17/data/server.key \
  -subj "/CN=$(hostname)"
```

### Service Won't Start

**Symptom:** Postgres service fails to start

**Solution:**

- Check Postgres logs:

```bash
# Systemd
sudo journalctl -u postgresql-17 -f --no-pager

# Debian
sudo tail -f /var/log/postgresql/postgresql-17-main.log

# RHEL
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

- Verify configuration syntax:

```bash
sudo -u postgres /usr/pgsql-17/bin/postgres -D /var/lib/pgsql/17/data -C config_file
```

- Check for port conflicts:

```bash
netstat -tnlp | grep 5432
```

### Extension Installation Fails

**Symptom:** Spock or Snowflake extension fails to install

**Solution:**

- Verify extensions are included in pgEdge packages:

```bash
# Check for extension files
ls -la /usr/pgsql-17/share/extension/spock*
ls -la /usr/pgsql-17/share/extension/snowflake*
```

- Check `shared_preload_libraries` is set correctly
- Restart Postgres after configuration changes
- Manually test extension creation:

```bash
sudo -u postgres psql -c "CREATE EXTENSION spock CASCADE;"
```

### Connection Refused

**Symptom:** Cannot connect to Postgres after setup

**Solution:**

- Verify Postgres is listening on correct port:

```bash
sudo netstat -tnlp | grep postgres
```

- Check `listen_addresses` is set to '0.0.0.0'
- Verify firewall allows connections:

```bash
sudo firewall-cmd --list-all  # RHEL
sudo ufw status               # Debian
```

- Check `pg_hba.conf` for appropriate rules:

```bash
sudo -u postgres cat /var/lib/pgsql/17/data/pg_hba.conf
```

### User Creation Fails

**Symptom:** Database user creation fails

**Solution:**

- Verify Postgres is running
- Check connection via Unix socket:

```bash
sudo -u postgres psql -c "SELECT version();"
```

- Verify `python3-psycopg2` is installed
- Check for existing users:

```bash
sudo -u postgres psql -c "\du"
```

## Notes

!!! tip "Configuration Management"
    Postgres configuration is managed via the Ansible `blockinfile` module. Manual changes outside the managed block are preserved.

## See Also

- [Configuration Reference](../configuration.md) - Complete variable documentation
- [role_config](role_config.md) - Configuration variables reference
- [install_pgedge](install_pgedge.md) - Required prerequisite for Postgres installation
- [setup_pgedge](setup_pgedge.md) - Configures Spock replication
- [setup_patroni](setup_patroni.md) - Configures HA cluster management
