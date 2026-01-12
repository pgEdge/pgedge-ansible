# install_backrest

## Overview

The `install_backrest` role installs pgBackRest, a modern backup and restore solution for PostgreSQL. It also ensures the cron service is installed and available for scheduling automated backups.

## Purpose

The role performs the following tasks:

- installs pgBackRest from pgEdge repositories.
- installs the cron service for backup scheduling.
- prepares the system for PostgreSQL backup and recovery operations.
- enables both full and incremental backup capabilities.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `init_server`: You must initialize all servers
- `install_repos`: You must configure repositories first

## When to Use

Execute this role on **all pgedge hosts** and **backup servers** where pgBackRest will be used:

```yaml
# Install on PostgreSQL nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest

# Install on dedicated backup servers
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
```

## Parameters

This role uses no custom parameters. All configuration is handled through package installation.

## Tasks Performed

### 1. Package Installation

Installs the following packages:

!!! note "Backup and Restore"
    This role only installs pgBackRest. Actual backup configuration, repository setup, and scheduling is handled by the `setup_backrest` role.

**pgBackRest Package:**

This role focuses on installing the `pgedge-pgbackrest` system package for the pgBackRest backup utility. This package includes all standard backup and restore tools and provides both CLI utilities and configuration management.

**Cron Service:**

The `setup_backrest` role requires cron to configure backup schedules. Cron packaging is not always standardized across Linux variants. As a result, we use different packages for the main Linux families:

- RHEL/Rocky: `cronie` - Vixie cron implementation
- Debian/Ubuntu: `cron` - Standard cron daemon

### 2. Retry Logic

The role includes robust retry logic, and will:

- attempt installation up to 5 times.
- wait 20 seconds between retries.
- handle transient network or repository issues.
- include lock timeout of 300 seconds for package manager.
- update package cache before installation.

## Files Generated

This role installs system packages which create:

### Binaries

- `/usr/bin/pgbackrest` - Main pgBackRest executable

### Configuration Directories

- `/etc/pgbackrest/` - Default configuration directory (empty until `setup_backrest`)
- `/var/log/pgbackrest/` - Log directory

## Platform-Specific Behavior

### Debian-Family

- Installs `cron` package for scheduling
- Uses APT package manager
- Package: `pgedge-pgbackrest`
- Cron service: `cron.service`

### RHEL-Family

- Installs `cronie` package for scheduling
- Uses DNF package manager
- Package: `pgedge-pgbackrest`
- Cron service: `crond.service`

## Example Usage

### Basic Installation

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
```

### Install on All Cluster Components

```yaml
# Install on PostgreSQL nodes (backup clients)
- hosts: pgedge
  roles:
    - install_repos
    - install_backrest

# Install on dedicated backup server (backup repository)
- hosts: backup
  roles:
    - install_repos
    - install_backrest
```

### Installation with Other Components

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    - install_pgedge
    - install_backrest
    - setup_postgres
    - setup_backrest
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- make no changes if the packages are already installed.
- update to the latest package version if available.
- make no configuration changes (the `setup_backrest` role handles those).

## Notes

You should verify pgBackRest is installed correctly after installation:

```bash
pgbackrest version
```
