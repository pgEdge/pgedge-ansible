# install_pgedge

## Overview

The `install_pgedge` role installs pgEdge Enterprise Postgres packages on target systems. This includes Postgres server binaries, the Spock logical replication extension, Snowflake extension, and Python Postgres drivers.

## Purpose

This role performs the following tasks:

- Installs pgEdge Enterprise Postgres server packages.
- Installs pgEdge extensions (Spock, Snowflake).
- Installs the Python Postgres adapter (psycopg2).
- Ensures all components match the configured Postgres version.

## Role Dependencies

- `role_config`: Provides Postgres version and configuration
- `install_repos`: You must run this role first to configure package repositories

## When to Use

Execute this role on **all pgedge hosts** after configuring repositories and before setting up Postgres instances:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

## Parameters

This role uses the following configuration parameters:

* `pg_version`

## Tasks Performed

### 1. Package Installation

Installs Postgres server and client binaries, along with supplementary packages.

**pgEdge software and extensions:**

- The lolor extension provides Large Object (LOB) support in logical replication.
- The Snowflake extension provides unique ID generation.
- The Spock extension provides bidirectional logical replication.

**Community and other popular tools:**

- [pgAdmin](https://www.pgadmin.org/) GUI administration tool
- [PGAudit](https://www.pgaudit.org/) query and session auditing extension
- [PgBouncer](https://www.pgbouncer.org/) connection pooler
- [pgvector](https://github.com/pgvector/pgvector) Vector database extension
- [PostGIS](https://postgis.net/) geospatial extension for Geographic Information Systems

**Python Postgres Adapter:**

- `pgedge-python3-psycopg2` - Python database adapter

### 2. Retry Logic

The role includes robust retry logic:

- attempts installation up to 5 times.
- waits 20 seconds between retries.
- handles transient network or repository issues.
- Ensures successful installation before proceeding

### 3. Version Pinning

- Always installs the latest available packages for the specified Postgres version
- Maintains consistency across all nodes in the cluster

## Files Generated

This role does not modify any files during execution aside from those the package installation generates.

## Platform-Specific Behavior

### Debian-Family

- Package name: `pgedge-enterprise-all-{{ pg_version }}`
- Uses APT package manager
- Packages install to `/usr/lib/postgresql/{{ pg_version }}/`
- Creates systemd service: `postgresql`

### RHEL-Family

- Package name: `pgedge-enterprise-all_{{ pg_version }}`
- Uses DNF package manager
- Installs to `/usr/pgsql-{{ pg_version }}/`
- Creates systemd service: `postgresql-{{ pg_version }}`

## Example Usage

### Basic Installation

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
```

### Install Specific Postgres Version

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pg_version: 16  # Install Postgres 16
  roles:
    - install_repos
    - install_pgedge
```

### Install on Multiple Node Groups

```yaml
# Install on primary cluster nodes
- hosts: pgedge
  roles:
    - install_repos
    - install_pgedge

# Install on backup server (for verification/restoration)
- hosts: backup
  roles:
    - install_repos
    - install_pgedge
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- update packages to latest versions if available.
- not disrupt running Postgres instances.

## Notes

!!! note "Automatic Updates"
    This role uses `state: latest` to ensure packages are updated to the newest version. This is intentional to maintain security and stability. Package updates will restart the Postgres service.
