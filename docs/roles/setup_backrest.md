# setup_backrest

## Overview

The `setup_backrest` role configures pgBackRest for PostgreSQL backup and recovery. It supports both SSH-based backups to a dedicated backup server and S3-compatible object storage. The role handles client and server configuration, SSH key distribution, backup user creation, initial backup, and automated backup scheduling.

## Purpose

The role performs the following tasks:

- configures pgBackRest on PostgreSQL nodes (clients).
- configures pgBackRest on dedicated backup servers.
- sets up SSH authentication for backup access.
- creates backup database user.
- configures PostgreSQL archive command.
- integrates with Patroni for HA clusters.
- takes initial bootstrap backup.
- schedules automated full and differential backups.
- supports both SSH and S3 backup repositories.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `install_backrest`: You must install pgBackRest
- `setup_postgres`: You must configure PostgreSQL
- `init_server`: You must generate SSH keys

## When to Use

Execute this role on **all pgedge hosts** and **backup servers** after PostgreSQL setup:

```yaml
# Configure backups on PostgreSQL nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - setup_backrest

# Configure dedicated backup server
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_backrest
    - setup_backrest
```

## Parameters

All parameters are inherited from `role_config`:

### Backup Repository Configuration

- `backup_repo_type` - Repository type: `ssh` or `s3` (default: `ssh`)
- `backup_repo_path` - Repository path (default: `/home/backrest`)
- `backup_repo_user` - OS user for backup operations (default: `{{ ansible_user_id }}`)
- `backup_repo_cipher_type` - Encryption algorithm (default: `aes-256-cbc`)
- `backup_repo_cipher` - Encryption key (auto-generated)

### SSH Backup Configuration

- `backup_host` - Backup server hostname (auto-detected from `backup` group)
- `backup_server` - Resolved backup server name

### S3 Backup Configuration

- `backup_repo_params` - Dictionary with S3 parameters:
  - `region` - AWS region
  - `endpoint` - S3 endpoint URL
  - `bucket` - S3 bucket name
  - `access_key` - AWS access key ID
  - `secret_key` - AWS secret access key

```yaml
backup_repo_params:
  region: us-west-2
  endpoint: s3.amazonaws.com
  bucket: my-pg-backups
  access_key: "{{ vault_aws_access_key }}"
  secret_key: "{{ vault_aws_secret_key }}"
```

### Backup User

- `backup_user` - Backup database user (default: `backrest`)
- `backup_password` - Backup user password (default: `secret`)

### Backup Retention

- `full_backup_count` - Full backups to retain (default: `1`)
- `diff_backup_count` - Differential backups to retain (default: `6`)

### Backup Scheduling

- `full_backup_schedule` - Cron schedule for full backups (default: `10 0 * * 0` - Sunday at 00:10)
- `diff_backup_schedule` - Cron schedule for differential backups (default: `10 0 * * 1-6` - Mon-Sat at 00:10)

## Tasks Performed

### Client Configuration (PostgreSQL Nodes)

#### 1. pgBackRest Configuration

Creates `/etc/pgbackrest/pgbackrest.conf`:

**Stanza Section `[pgedge-<cluster>-<zone>]`:**

- `pg1-port` - PostgreSQL port
- `pg1-path` - PostgreSQL data directory
- `pg1-user` - postgres OS user
- `pg1-database` - Connection database

**Global Section `[global]`:**

- `log-path` - `/var/log/pgbackrest`
- `start-fast` - Force checkpoint at backup start
- `repo1-path` - Repository path
- `repo1-retention-full` - Full backup retention count
- `repo1-retention-diff` - Differential backup retention count
- `repo1-cipher-type` - Encryption algorithm
- `repo1-cipher-pass` - Encryption passphrase

**SSH Repository (backup_type: ssh):**

- `repo1-type` - `posix`
- `repo1-host` - Backup server hostname
- `repo1-host-user` - Backup repository user
- `repo1-hardlink` - Enable hardlinks for efficiency

**S3 Repository (backup_type: s3):**

- `repo1-type` - `s3`
- `repo1-s3-region` - AWS region
- `repo1-s3-endpoint` - S3 endpoint
- `repo1-s3-bucket` - S3 bucket name
- `repo1-s3-key` - Access key
- `repo1-s3-key-secret` - Secret key

#### 2. SSH Access Configuration (SSH mode only)

- Adds backup server's SSH host key to known_hosts
- Distributes postgres user's SSH public key to backup server
- Ensures SSH connectivity for backup transfers

#### 3. PostgreSQL Configuration

**Standalone Clusters:**

Modifies `postgresql.conf`:

- Sets `archive_mode = on`
- Sets `archive_command` to pgBackRest archive-push command

**HA Clusters:**

Updates Patroni DCS configuration:

- Configures archive_command through Patroni
- Ensures consistent configuration across cluster
- Patroni manages PostgreSQL restart

#### 4. Backup User Creation

- Creates backup database user with REPLICATION privilege
- Adds pg_hba.conf entry for backup server connections
- Creates `.pgpass` entry for automated authentication

#### 5. Initial Backup (S3 mode or first node)

- Takes initial full backup (stanza-create + backup)
- Verifies backup repository is functional
- Required before automated backups can run

#### 6. Automated Backup Scheduling

Creates cron jobs for postgres user:

- Full backup: Runs weekly (Sunday default)
- Differential backup: Runs daily (Monday-Saturday default)
- Includes retention policy enforcement

### Server Configuration (Backup Nodes)

#### 1. pgBackRest Configuration

Creates `/etc/pgbackrest/pgbackrest.conf`:

**Stanza Section `[pgedge-<cluster>-<zone>]`:**

Lists all PostgreSQL nodes in zone:

- `pg1-host`, `pg2-host`, etc. - Node hostnames
- `pg1-host-user` - postgres user
- `pg1-port` - PostgreSQL port
- `pg1-path` - Data directory
- `pg1-user` - postgres user
- `pg1-database` - Connection database

**Global Section:**

Same as client configuration with appropriate repository settings.

#### 2. SSH Access Configuration

- Authorizes SSH keys from all PostgreSQL nodes
- Adds all PostgreSQL nodes to known_hosts
- Creates `.pgpass` for database connections

#### 3. Initial Backup

- Connects to first node in zone
- Takes initial stanza-create and full backup
- Verifies backup functionality

#### 4. Automated Backup Scheduling

Creates cron jobs for backup repository user:

- Full and differential backups
- Runs from backup server, connects to PostgreSQL nodes via SSH

## Files Generated

### Configuration Files

**On PostgreSQL Nodes:**

- `/etc/pgbackrest/pgbackrest.conf` - pgBackRest configuration
- `~postgres/.ssh/known_hosts` - SSH host keys (SSH mode)
- `~postgres/.pgpass` - Backup user credentials

**On Backup Servers:**

- `/etc/pgbackrest/pgbackrest.conf` - pgBackRest configuration
- `~<backup_user>/.ssh/authorized_keys` - Authorized SSH keys
- `~<backup_user>/.ssh/known_hosts` - PostgreSQL node SSH keys
- `~<backup_user>/.pgpass` - Backup user credentials

### Backup Repository

**SSH Mode:**

- `<backup_repo_path>/archive/<stanza>/` - WAL archive
- `<backup_repo_path>/backup/<stanza>/` - Backup files
- `<backup_repo_path>/backup/<stanza>/backup.info` - Backup metadata

**S3 Mode:**

- `s3://<bucket>/<repo_path>/archive/<stanza>/` - WAL archive
- `s3://<bucket>/<repo_path>/backup/<stanza>/` - Backup files

### Cron Jobs

- Full backup cron job in postgres/backup_user crontab
- Differential backup cron job in postgres/backup_user crontab

### Log Files

- `/var/log/pgbackrest/` - pgBackRest operation logs

## Platform-Specific Behavior

### All Supported Platforms

This role behaves identically on:

- Debian 12
- Rocky Linux 9

Platform differences are handled through variables and pgBackRest is cross-platform.

## Example Usage

### SSH-Based Backups to Dedicated Server

```yaml
# PostgreSQL nodes
- hosts: pgedge
  vars:
    backup_repo_type: ssh
  roles:
    - setup_backrest

# Dedicated backup server
- hosts: backup
  vars:
    backup_repo_path: /backups/pgedge
  roles:
    - install_backrest
    - setup_backrest
```

### S3-Based Backups

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    backup_repo_type: s3
    backup_repo_params:
      region: us-east-1
      endpoint: s3.amazonaws.com
      bucket: prod-pg-backups
      access_key: "{{ vault_aws_access }}"
      secret_key: "{{ vault_aws_secret }}"
  roles:
    - setup_backrest
```

### Custom Retention and Scheduling

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    full_backup_count: 2
    diff_backup_count: 14
    full_backup_schedule: "0 2 * * 0"  # Sunday at 2:00 AM
    diff_backup_schedule: "0 2 * * 1-6"  # Mon-Sat at 2:00 AM
  roles:
    - setup_backrest
```

### HA Cluster with Backups

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    backup_repo_type: ssh
  roles:
    - setup_postgres
    - setup_etcd
    - setup_patroni
    - setup_backrest

- hosts: backup
  roles:
    - init_server
    - install_backrest
    - setup_backrest
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- regenerate configuration files each run to incorporate changes.
- only create the backup database user if it doesn't exist.
- not overwrite an existing pgBackRest stanza.

## Notes

!!! important "Initial Backup Required"
    An initial full backup must complete successfully before automated backups or WAL archiving will work. The role handles this automatically.

!!! info "SSH vs S3"
    SSH mode requires a dedicated backup server but provides simplicity. S3 mode eliminates the backup server but requires cloud access and credentials.

!!! warning "Encryption Keys"
    The `backup_repo_cipher` is auto-generated based on cluster name and zone. Losing this key makes backups unrecoverable. Store it securely!

!!! note "Retention Policy"
    pgBackRest automatically expires old backups based on retention settings. Set `full_backup_count` and `diff_backup_count` appropriately for your RTO/RPO requirements.

!!! tip "Backup Verification"
    Regularly verify backups:
    ```bash
    # List backups
    sudo -u postgres pgbackrest --stanza=pgedge-demo-1 info

    # Check backup validity
    sudo -u postgres pgbackrest --stanza=pgedge-demo-1 check

    # Test restore (to different location)
    sudo -u postgres pgbackrest --stanza=pgedge-demo-1 restore --delta --target-path=/tmp/restore-test
    ```

!!! warning "HA Cluster Integration"
    For HA clusters, this role integrates with Patroni to configure archiving cluster-wide. Manual changes to archive_command may be overwritten.

!!! note "Backup User Permissions"
    The backup user needs REPLICATION privilege to backup from standby servers and to use pg_start_backup/pg_stop_backup functions.
