# install_pgedge

The `install_pgedge` role installs pgEdge Enterprise Postgres packages on
target systems. The role installs Postgres server binaries, the Spock logical
replication extension, Snowflake extension, and Python Postgres drivers.

The role performs the following tasks on inventory hosts:

- Install the pgEdge Enterprise Postgres meta-package.
- Install pgEdge extensions including Spock and Snowflake.
- Install the Python Postgres adapter for database connectivity.
- Ensure all components match the configured Postgres version.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides Postgres version and configuration variables.
- `install_repos` configures pgEdge package repositories before installation.

## When to Use

Execute this role on all pgedge hosts after configuring repositories and
before setting up Postgres instances.

In the following example, the playbook installs pgEdge packages after
repository configuration:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

## Configuration

This role uses the following parameter from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_version` | Specify the Postgres version to install. |

## How It Works

The role installs the pgEdge Enterprise meta-package, which includes all
components that a pgEdge deployment needs. The role applies retry logic,
attempting installation up to five times with twenty-second delays between
attempts to handle transient network or repository issues.

The pgEdge Enterprise package includes the following components:

- Spock provides bidirectional logical replication for multi-master setups.
- Snowflake provides unique ID generation across cluster nodes.
- LOLOR provides Large Object (LOB) support in logical replication.
- pgAdmin provides a GUI for Postgres administration.
- PGAudit provides query and session auditing.
- PgBouncer provides connection pooling.
- pgvector provides vector database capabilities.
- PostGIS provides geospatial extensions.

## Usage Examples

In the following example, the playbook installs Postgres 17 using the default
version:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

In the following example, the playbook installs a specific Postgres version:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pg_version: 16
  roles:
    - install_repos
    - install_pgedge
```

## Platform-Specific Behavior

On Debian-based systems, the role uses APT to install the
`pgedge-enterprise-all-{{ pg_version }}` package and binaries land in
`/usr/lib/postgresql/{{ pg_version }}/`. On RHEL-based systems, the role uses
DNF to install `pgedge-enterprise-all_{{ pg_version }}` and binaries land in
`/usr/pgsql-{{ pg_version }}/`.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role may
update packages to the latest available version when newer versions exist; it
does not disrupt running Postgres instances during package updates.
