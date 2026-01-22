# install_pgedge

The `install_pgedge` role installs pgEdge Enterprise Postgres packages on
target systems. The role installs Postgres server binaries, the Spock
logical replication extension, Snowflake extension, and Python Postgres
drivers.

The role performs the following tasks on inventory hosts:

- Install pgEdge Enterprise Postgres server packages.
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

This role utilizes the collection-wide configuration parameter for Postgres
version as described in the [Configuration section](../configuration/index.md).

Set the parameter in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    pg_version: 17
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `pg_version` | Specify the Postgres version to install. |

## How It Works

The role installs the pgEdge Enterprise meta-package which includes all
components that a pgEdge deployment needs.

1. Install the pgEdge Enterprise package.
    - Install the meta-package containing Postgres server and client binaries.
    - Include pgEdge extensions: Spock, Snowflake, and lolor.
    - Include community tools: pgAdmin, PGAudit, PgBouncer, pgvector, and
      PostGIS.
    - Install the `pgedge-python3-psycopg2` Python database adapter.

2. Apply retry logic for reliability.
    - Attempt installation up to 5 times to handle transient failures.
    - Wait 20 seconds between retries.
    - Handle transient network or repository issues gracefully.

3. Maintain version consistency.
    - Install packages matching the specified `pg_version` parameter.
    - Ensure consistency across all nodes in the cluster.

The pgEdge Enterprise package includes these components:

- **lolor** provides Large Object (LOB) support in logical replication.
- **Snowflake** provides unique ID generation across cluster nodes.
- **Spock** provides bidirectional logical replication for multi-master.
- **pgAdmin** provides GUI administration for Postgres.
- **PGAudit** provides query and session auditing.
- **PgBouncer** provides connection pooling.
- **pgvector** provides vector database capabilities.
- **PostGIS** provides geospatial extensions.

!!! note "Automatic Updates"
    This role uses `state: latest` to ensure packages update to the newest
    version. Package updates may restart the Postgres service.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook installs pgEdge packages using the
default Postgres version:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

### Specific Postgres Version

In the following example, the playbook installs Postgres 16:

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

### Multiple Node Groups

In the following example, the playbook installs pgEdge on primary nodes and
a backup server:

```yaml
# Install on primary cluster nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge

# Install on backup server for verification and restoration
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

## Artifacts

This role installs system packages that create files based on the operating
system. The role does not modify additional files during execution.

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, the role uses these packages and paths:

| Setting | Value |
|---------|-------|
| Package name | `pgedge-enterprise-all-{{ pg_version }}` |
| Package manager | APT |
| Install path | `/usr/lib/postgresql/{{ pg_version }}/` |
| Service name | `postgresql` |

### RHEL Family

On RHEL-based systems, the role uses these packages and paths:

| Setting | Value |
|---------|-------|
| Package name | `pgedge-enterprise-all_{{ pg_version }}` |
| Package manager | DNF |
| Install path | `/usr/pgsql-{{ pg_version }}/` |
| Service name | `postgresql-{{ pg_version }}` |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role may update these items on subsequent runs:

- Update packages to the latest available version when newer versions exist.

The role does not disrupt running Postgres instances during package updates.
