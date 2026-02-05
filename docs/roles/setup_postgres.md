# setup_postgres

The `setup_postgres` role initializes and configures Postgres instances for
pgEdge deployments. The role handles standalone and high availability
configurations by managing database initialization, SSL certificates, user
creation, and extension installation.

The role performs the following tasks on inventory hosts:

- Initialize the Postgres data directory so deployments begin in a clean state.
- Generate SSL certificates to enable encrypted client and server connections.
- Configure Postgres for logical replication so Spock can synchronize data.
- Set up `pg_hba.conf` to establish secure authentication rules.
- Create database users including admin, replication, and pgedge accounts.
- Create and configure databases specified in the inventory file.
- Install the Spock and Snowflake extensions in all configured databases.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_pgedge` installs pgEdge packages including Postgres.

## When to Use

Execute this role on all pgedge hosts after installing Postgres.

In the following example, the playbook invokes the role after installing
the required repositories and pgEdge packages:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
```

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    pg_data: /var/lib/pgsql/17/data
    pg_port: 5432
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `pg_data` | Postgres data directory path for initialization. |
| `pg_port` | Port number where Postgres listens for connections. |
| `pg_version` | Postgres version to configure. |
| `db_names` | Databases to create during setup. |
| `db_user` | Admin user for cluster management. |
| `db_password` | Password for the admin database user. |
| `custom_hba_rules` | Custom authentication rules for `pg_hba.conf`. |
| `pgedge_user` | pgEdge user for node communication. |
| `pgedge_password` | Password for the pgEdge user account. |
| `replication_user` | User for Patroni streaming replication. |
| `replication_password` | Password for the replication user. |
| `spock_exception_behaviour` | Spock replication exception handling behavior. |
| `zone` | Snowflake zone identifier for the server. |
| `is_ha_cluster` | Enable high availability cluster configuration mode. |

## How It Works

The role operates differently depending on the deployment mode selected in
the inventory configuration.

### Standalone Setup

When the `is_ha_cluster` parameter is `false`, the role performs these steps:

1. Initialize the Postgres instance.
    - Run `postgresql-{{ pg_version }}-setup initdb` on RHEL systems to create
      the data directory.
    - Use the auto-initialized cluster on Debian systems from the package
      installation.

2. Generate SSL certificates.
    - Generate a self-signed SSL certificate and private key for encrypted
      connections.
    - Store files at `{{ pg_data }}/server.crt` and `{{ pg_data }}/server.key`.
    - Set secure permissions with mode 600 on the key and mode 644 on the
      certificate.
    - Configure Postgres to use the SSL certificates for client connections.

3. Configure Postgres settings.
    - Set the port to the value specified in `pg_port`.
    - Configure Postgres to listen on all available IPv4 addresses.
    - Enable archive mode for later configuration of archive command.
    - Increase replication slots and WAL senders to 16 for cluster capacity.
    - Enable hot standby feedback to avoid query cancellation on replicas.
    - Enable commit timestamps for Spock conflict resolution.
    - Add spock, snowflake, and `pg_stat_statements` to preload libraries.
    - Set Spock conflict resolution to `last_update_wins`.
    - Enable Spock DDL replication for schema synchronization.
    - Set the default Spock exception behavior to discard the current
      transaction.
    - Configure Spock to automatically add new tables to replication sets.
    - Set the Snowflake zone to the current server zone.

4. Configure `pg_hba.conf` authentication rules.
    - Configure local peer access for the `postgres` user.
    - Enable localhost connections via SCRAM-SHA-256 authentication.
    - Allow network access for `pgedge_user` and `db_user` from all cluster
      nodes.
    - Apply custom rules from the `custom_hba_rules` variable when present.

5. Start the Postgres service.
    - Start the Postgres service using the system service manager.
    - Enable the service for automatic startup on boot.
    - Wait for the service to be ready before proceeding.

6. Create database users.
    - Create the admin user specified in `db_user` with superuser privileges.
    - Create the pgEdge user specified in `pgedge_user` with superuser,
      replication, and bypassrls privileges.

7. Create databases and install extensions.
    - Create all databases specified in the `db_names` parameter.
    - Install the Spock extension in all configured databases.
    - Install the Snowflake extension in all configured databases.

!!! note "Shared Preload Libraries"
    The role modifies the `shared_preload_libraries` parameter. If this is a
    pre-existing instance, you must restart Postgres for changes to this
    setting to take effect.

### High Availability Setup

When the `is_ha_cluster` parameter is `true`, the role performs all standalone
setup tasks plus additional high availability configuration.

1. Manage the Postgres service on the primary node.
    - Stop the Postgres service on the primary node.
    - Disable automatic startup because Patroni manages the service.
    - Restart Postgres temporarily for initial configuration.

2. Configure the replication user on the primary node.
    - Create the replication user specified in `replication_user` for Patroni
      streaming replication.
    - Add `pg_hba.conf` rules for the replication user from zone nodes.
    - Configure proxy access for HAProxy health checks.
    - Create a `.pgpass` entry for automated connections from the replication
      user.

3. Configure replica nodes.
    - Stop the Postgres service on replica nodes.
    - Disable automatic startup because Patroni manages the service.
    - Erase the `pg_data` directory when present because Patroni rebuilds the
      directory during bootstrap.

!!! note "Postgres Service Management"
    If the Patroni service is running, the role assumes the bootstrapping
    process is complete and skips these steps. The role does not stop Postgres
    or erase the data directory in this case.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook deploys a standalone Postgres instance
with two databases and a custom admin user:

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

In the following example, the playbook deploys a high availability cluster
with Patroni and etcd managing failover:

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

### Custom Authentication Rules

In the following example, the playbook adds custom `pg_hba.conf` rules to
allow specific users access from designated networks:

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

### Multiple Databases

In the following example, the playbook creates multiple databases with Spock
and Snowflake extensions installed in each:

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

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ pg_data }}/server.crt` | New | SSL certificate file with mode 644 for encrypted client connections. |
| `{{ pg_data }}/server.key` | New | SSL private key file with mode 600 to secure the certificate. |
| `~postgres/.pgpass` | New | Password file to enable automated database connections. |
| `{{ pg_config_dir }}/postgresql.conf` | Modified | Postgres settings configured for pgEdge deployment. |
| `{{ pg_data }}/pg_hba.conf` | Modified | Authentication rules configured for users and nodes. |

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, Postgres auto-initializes during package installation
and the role uses these paths:

| Setting | Value |
|---------|-------|
| Data directory | `/var/lib/postgresql/{{ pg_version }}/main` |
| Config directory | `/etc/postgresql/{{ pg_version }}/main` |
| Service name | `postgresql@{{ pg_version }}-main` |

The role does not run manual initdb on Debian systems.

### RHEL Family

On RHEL-based systems, the role must initialize Postgres manually and uses
these paths:

| Setting | Value |
|---------|-------|
| Data directory | `/var/lib/pgsql/{{ pg_version }}/data` |
| Config directory | `/var/lib/pgsql/{{ pg_version }}/data` |
| Service name | `postgresql-{{ pg_version }}` |

The role runs `postgresql-{{ pg_version }}-setup initdb` to create the data
directory on RHEL systems.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Initialize the Postgres data directory only when the directory is missing.
- Preserve existing SSL certificates without overwriting.
- Create users and databases only when they do not exist.
- Install extensions only when they are absent.

The role may update these items on subsequent runs:

- Update configuration blocks in `postgresql.conf` to match inventory settings.
- Update `pg_hba.conf` rules to match the current configuration.
- Update user passwords when the inventory values change.
- Adjust the Postgres service state to match the desired state.

!!! tip "Configuration Management"
    Postgres configuration uses the Ansible `blockinfile` module. The role
    preserves manual changes outside the managed block.
