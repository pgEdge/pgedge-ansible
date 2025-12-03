# install_backrest

## Overview

The `install_backrest` role installs pgBackRest, a modern backup and restore solution for PostgreSQL. It also ensures the cron service is installed and available for scheduling automated backups.

## Purpose

- Install pgBackRest from pgEdge repositories
- Install cron service for backup scheduling
- Prepare system for PostgreSQL backup and recovery operations
- Enable both full and incremental backup capabilities

## Role Dependencies

- `role_config` - Provides shared configuration variables
- `init_server` - All servers must be initialized
- `install_repos` - Must configure repositories first

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

- `pgedge-pgbackrest` - pgBackRest backup utility
- Includes all backup and restore tools
- Provides both CLI and configuration management

**Cron Service:**

- RHEL/Rocky: `cronie` - Vixie cron implementation
- Debian/Ubuntu: `cron` - Standard cron daemon
- Required for automated backup scheduling
- Enables `setup_backrest` to configure backup schedules

### 2. Retry Logic

The role includes robust retry logic:

- Attempts installation up to 5 times
- Waits 20 seconds between retries
- Handles transient network or repository issues
- Includes lock timeout of 300 seconds for package manager
- Updates package cache before installation

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

This role is fully idempotent:

- Package installation is idempotent (no changes if already installed)
- Will update to latest package version if available
- Safe to re-run multiple times
- No configuration changes are made (handled by `setup_backrest`)

## Troubleshooting

### Package Not Found

**Symptom:** pgbackrest package not found in repositories

**Solution:**

- Verify `install_repos` role completed successfully
- Update package cache:

```bash
# Debian/Ubuntu
sudo apt update
apt-cache search pgbackrest

# RHEL/Rocky
sudo dnf makecache
dnf search pgbackrest
```

- Verify pgEdge repository is enabled:

```bash
# Debian/Ubuntu
cat /etc/apt/sources.list.d/pgedge.sources

# RHEL/Rocky
cat /etc/yum.repos.d/pgedge.repo
```

### Cron Package Conflicts

**Symptom:** Cron installation fails due to conflicts

**Solution:**

- Check for existing cron installations:

```bash
# Debian/Ubuntu
dpkg -l '*cron*'

# RHEL/Rocky
rpm -qa | grep cron
```

- Remove conflicting packages if safe:

```bash
# RHEL only (if anacron conflicts)
sudo dnf remove cronie-anacron
sudo dnf install cronie
```

### Lock Timeout on Debian

**Symptom:** Package manager lock timeout

**Solution:**

- Wait for other package operations to complete
- Check for hung package manager processes:

```bash
ps aux | grep -E 'apt|dpkg'
```

- The role uses a 300-second timeout which should be sufficient for most systems

### Installation Fails After Retries

**Symptom:** Installation fails after 5 attempts

**Solution:**

- Check network connectivity to pgEdge repositories
- Verify repository GPG keys are installed
- Check system logs:

```bash
# Debian/Ubuntu
sudo tail -f /var/log/apt/term.log

# RHEL/Rocky
sudo tail -f /var/log/dnf.log
```

- Manually attempt installation:

```bash
# Debian/Ubuntu
sudo apt install pgedge-pgbackrest

# RHEL/Rocky
sudo dnf install pgedge-pgbackrest
```

### Cron Service Not Starting

**Symptom:** Cron package installed but service not running

**Solution:**

- Check cron service status:

```bash
# Debian/Ubuntu
sudo systemctl status cron

# RHEL/Rocky
sudo systemctl status crond
```

- Start and enable cron service:

```bash
# Debian/Ubuntu
sudo systemctl enable --now cron

# RHEL/Rocky
sudo systemctl enable --now crond
```

### pgBackRest Binary Not Found

**Symptom:** `pgbackrest` command not found after installation

**Solution:**

- Verify package installation:

```bash
# Debian/Ubuntu
dpkg -L pgedge-pgbackrest | grep bin

# RHEL/Rocky
rpm -ql pgedge-pgbackrest | grep bin
```

- Check if binary is in PATH:

```bash
which pgbackrest
ls -la /usr/bin/pgbackrest
```

## Notes

After installation, verify pgBackRest is installed correctly:

```bash
pgbackrest version
```

## See Also

- [Configuration Reference](../configuration.md) - Backup configuration variables
- [install_repos](install_repos.md) - Required prerequisite for repository configuration
- [setup_backrest](setup_backrest.md) - Configures backups and schedules
