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
| `pg_parameters` | Postgres configuration parameters applied over the collection's defaults. |
| `pg_allow_restart` | Restart Postgres when a changed parameter needs it. |

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
3. Write the Postgres configuration: the parameters the collection requires
   (such as port, listen addresses, `wal_level` and the archive commands), the
   collection's defaults, and the inventory's `pg_parameters`. See
   [pg_parameters](../configuration/postgres.md#pg_parameters).
4. Configure `pg_hba.conf` with least-privilege rules for all known users
   and databases. Apply any additional rules from `custom_hba_rules`.
5. Start and enable the Postgres service. If the service was already running
   and the configuration changed, reload it. If Postgres then reports
   parameters waiting on a restart, restart it, or report them when
   `pg_allow_restart` is `false`. Nodes restart one at a time, so the rest of
   the cluster stays available.
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

On the first node of an HA zone, this role writes only the parameters Postgres
needs to run before Patroni takes over. Patroni keeps the rest of the
configuration in its store, which `setup_patroni` maintains.

!!! note "Shared Preload Libraries"
    A change to `shared_preload_libraries` only takes effect after a restart.
    On a simple cluster this role restarts Postgres to apply it, unless
    `pg_allow_restart` is `false`.

### Logical Decoding Output Plugins

The fix for
[CVE-2026-6471](https://github.com/advisories/GHSA-r26j-h78w-pjqm) stops
Postgres from loading a logical decoding output plugin that
`output_plugin_libraries` does not name, so Spock cannot replicate until
`spock_output` appears in that list. The role sets the parameter to
`pgoutput, test_decoding, spock_output`, which also names the two in-tree
plugins so ordinary logical replication and `pg_recvlogical` keep working.

The parameter arrived in a different minor release for each Postgres major,
and Postgres refuses to start when its configuration names a parameter it
does not recognize. The role therefore asks the Postgres binary which
parameters the installed release recognizes, records the answer in
`pg_supports_output_plugin_libraries`, and writes the parameter only where it
exists. Releases predating the fix neither restrict plugin loading nor
recognize the parameter.

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

On Debian-based systems, the package auto-initializes a default cluster named
`main` during installation. Its data directory is
`/var/lib/postgresql/{{ pg_version }}/main`, its configuration directory is
`/etc/postgresql/{{ pg_version }}/main`, and its service name is
`postgresql@{{ pg_version }}-main`.

The role creates a cluster named by `cluster_name` with its data in `pg_data`
and its configuration in `/etc/postgresql/{{ pg_version }}/{{ cluster_name }}`.
Its service name is `postgresql@{{ pg_version }}-{{ cluster_name }}`.
When that configuration directory still holds `postgresql.conf` or
`pg_hba.conf` but `pg_data` holds no cluster, the role stops the cluster the
files describe and removes them before creating the new one. That covers a
cluster whose data was erased, and `cluster_name: main` with a `pg_data` other
than the default: the package's `main` cluster is stopped and its configuration
replaced, but its data directory is left in place.

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
    preserves manual changes made outside the managed block. The block itself
    is rewritten on every run, so a parameter removed from `pg_parameters` is
    removed from the file. Set parameters through `pg_parameters`, not by
    editing the block.
