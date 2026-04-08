# setup_postgres

The `setup_postgres` role initializes and configures Postgres instances for
pgEdge deployments. The role handles standalone and high availability
configurations by managing database initialization, SSL certificates, user
creation, and extension installation.

The role performs the following tasks on inventory hosts:

- Initialize the Postgres data directory for a clean starting state.
- Generate a self-signed TLS certificate for encrypted connections.
- Configure Postgres for logical replication so Spock can synchronize data.
- Set up `pg_hba.conf` with least-privilege authentication rules.
- Create database users including admin, pgEdge, and replication accounts.
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

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_data` | Postgres data directory path for initialization. |
| `pg_port` | Port number where Postgres listens for connections. |
| `pg_version` | Postgres version to configure. |
| `db_names` | Databases to create during setup. |
| `db_user` | Admin user for cluster management. |
| `db_password` | Password for the admin database user. |
| `custom_hba_rules` | Custom authentication rules for `pg_hba.conf`. |
| `pgedge_user` | pgEdge user for node-to-node Spock connections. |
| `pgedge_password` | Password for the pgEdge user account. |
| `replication_user` | User for Patroni streaming replication. |
| `replication_password` | Password for the replication user. |
| `zone` | Snowflake zone identifier for the server. |
| `is_ha_cluster` | Enable high availability cluster configuration mode. |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

The role operates differently depending on whether `is_ha_cluster` is `true`
or `false`.

### Standalone Setup

When `is_ha_cluster` is `false`, the role performs the following steps:

1. Initialize the Postgres data directory. On RHEL, the role runs
   `postgresql-{{ pg_version }}-setup initdb`. On Debian, the package
   auto-initializes the cluster.
2. Generate a self-signed SSL certificate and key, stored in `pg_data` with
   secure permissions.
3. Configure Postgres settings including port, listen addresses, WAL level
   (`logical`), replication slots, shared preload libraries (spock,
   snowflake, pg_stat_statements), and Spock conflict resolution settings.
4. Configure `pg_hba.conf` with least-privilege rules for all known users
   and databases. Apply any additional rules from `custom_hba_rules`.
5. Start and enable the Postgres service.
6. Create the admin user (`db_user`) and the pgEdge user (`pgedge_user`).
7. Create all databases listed in `db_names` and install the Spock and
   Snowflake extensions in each.

### High Availability Setup

When `is_ha_cluster` is `true`, the role performs all standalone setup tasks
and additionally:

- Designates the first node in each zone as the Patroni primary and stops
  Postgres on that node after initial configuration (Patroni takes over
  management).
- Stops Postgres on all other nodes in the zone and clears the data
  directory so Patroni can rebuild them as streaming replicas.
- Creates the Patroni `replication_user` and configures `pg_hba.conf`
  replication rules.

!!! note "Shared Preload Libraries"
    This role modifies `shared_preload_libraries`. If this is a pre-existing
    instance, a Postgres restart is required for the change to take effect.

## Usage Examples

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

## Artifacts

This role generates and modifies the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ pg_data }}/server.crt` | New | Self-signed SSL certificate for encrypted connections. |
| `{{ pg_data }}/server.key` | New | SSL private key with mode 600. |
| `~postgres/.pgpass` | New | Password file for automated database connections. |
| `{{ pg_config_dir }}/postgresql.conf` | Modified | Postgres settings configured for pgEdge deployment. |
| `{{ pg_data }}/pg_hba.conf` | Modified | Authentication rules configured for users and nodes. |

## Platform-Specific Behavior

On Debian-based systems, Postgres auto-initializes during package installation.
The data directory is `/var/lib/postgresql/{{ pg_version }}/main` and the
configuration directory is `/etc/postgresql/{{ pg_version }}/main`. The
service name is `postgresql@{{ pg_version }}-main`.

On RHEL-based systems, the role runs `postgresql-{{ pg_version }}-setup initdb`
to create the data directory at `/var/lib/pgsql/{{ pg_version }}/data`. The
service name is `postgresql-{{ pg_version }}`.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
initializes the data directory only when the directory is missing, preserves
existing SSL certificates, and creates users and databases only when they do
not exist. The role updates configuration blocks in `postgresql.conf` and
`pg_hba.conf` to match the current inventory settings.

!!! tip "Configuration Management"
    Postgres configuration uses the Ansible `blockinfile` module, which
    preserves manual changes made outside the managed block.
