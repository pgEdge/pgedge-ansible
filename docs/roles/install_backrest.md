# install_backrest

The `install_backrest` role installs pgBackRest, a modern backup and restore
solution for Postgres. The role also installs the cron service so the
`setup_backrest` role can schedule automated backups.

The role performs the following tasks on inventory hosts:

- Install the pgBackRest package from pgEdge repositories.
- Install the cron service for backup scheduling.
- Prepare the system for Postgres backup and recovery operations.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares the target system for package installation.
- `install_repos` configures pgEdge package repositories.

## When to Use

Execute this role on all pgedge hosts and backup servers where pgBackRest
will manage backups.

In the following example, the playbook installs pgBackRest on Postgres nodes
and a dedicated backup server:

```yaml
# Install on Postgres nodes
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

## Configuration

This role uses no custom parameters. All configuration happens through package
installation.

## How It Works

The role installs pgBackRest and cron packages using the system package
manager with retry logic to handle transient issues.

1. Install the pgBackRest package.
    - Install the `pgedge-pgbackrest` package from pgEdge repositories.
    - Provide CLI utilities for backup and restore operations.
    - Create the default configuration directory at `/etc/pgbackrest/`.

2. Install the cron service.
    - Install `cronie` on RHEL-family systems for Vixie cron support.
    - Install `cron` on Debian-family systems for the standard daemon.
    - Enable backup scheduling when `setup_backrest` runs later.

3. Apply retry logic for reliability.
    - Attempt installation up to 5 times to handle transient failures.
    - Wait 20 seconds between retries.
    - Use a 300-second lock timeout for the package manager.
    - Update the package cache before each installation attempt.

!!! note "Backup Configuration"
    This role only installs pgBackRest. The `setup_backrest` role handles
    backup configuration, repository setup, and scheduling.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook installs pgBackRest after configuring
the pgEdge repositories:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
```

### Full Cluster Installation

In the following example, the playbook installs pgBackRest as part of a
complete pgEdge deployment with backup configuration:

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

## Artifacts

This role installs system packages that create the following files.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/usr/bin/pgbackrest` | New | Main pgBackRest executable for backup and restore operations. |
| `/etc/pgbackrest/` | New | Default configuration directory; remains empty until `setup_backrest` runs. |
| `/var/log/pgbackrest/` | New | Log directory for pgBackRest operations. |

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, the role uses these packages and service names:

| Setting | Value |
|---------|-------|
| pgBackRest package | `pgedge-pgbackrest` |
| Cron package | `cron` |
| Cron service | `cron.service` |
| Package manager | APT |

### RHEL Family

On RHEL-based systems, the role uses these packages and service names:

| Setting | Value |
|---------|-------|
| pgBackRest package | `pgedge-pgbackrest` |
| Cron package | `cronie` |
| Cron service | `crond.service` |
| Package manager | DNF |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Skip package installation when the system already has packages at the
  required version.

The role may update these items on subsequent runs:

- Update packages to the latest available version when newer versions exist.
