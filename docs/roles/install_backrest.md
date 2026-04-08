# install_backrest

The `install_backrest` role installs PgBackRest, a modern backup and restore
solution for Postgres. The role also installs the cron service so the
`setup_backrest` role can schedule automated backups.

The role performs the following tasks on inventory hosts:

- Install the PgBackRest package from the pgEdge repository.
- Install the cron service for backup scheduling.
- Prepare the system for Postgres backup and recovery operations.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares the target system for package installation.
- `install_repos` configures pgEdge package repositories.

## When to Use

Execute this role on all pgedge hosts and backup servers where PgBackRest
will manage backups.

In the following example, the playbook installs PgBackRest on Postgres nodes
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

The role installs PgBackRest and cron packages using the system package
manager with retry logic to handle transient issues. The role attempts
installation up to five times with twenty-second delays and uses a
300-second lock timeout for the package manager.

The PgBackRest package installs:

- The `pgbackrest` CLI for backup and restore operations.
- The default configuration directory at `/etc/pgbackrest/`.
- The log directory at `/var/log/pgbackrest/`.

!!! note "Backup Configuration"
    This role only installs PgBackRest. The `setup_backrest` role handles
    backup configuration, repository setup, and scheduling.

## Usage Examples

In the following example, the playbook installs PgBackRest as part of a
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

This role installs system packages that create the following files:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/usr/bin/pgbackrest` | New | Main PgBackRest executable for backup and restore. |
| `/etc/pgbackrest/` | New | Default configuration directory, populated by `setup_backrest`. |
| `/var/log/pgbackrest/` | New | Log directory for PgBackRest operations. |

## Platform-Specific Behavior

On Debian-based systems, the role installs the `cron` package for the
standard cron daemon. On RHEL-based systems, the role installs `cronie` for
Vixie cron support. Both distributions install the `pgedge-pgbackrest` package.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
may update packages to the latest available version when newer versions exist.
