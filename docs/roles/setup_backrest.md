# setup_backrest

## Overview

The `setup_backrest` role configures pgBackRest for PostgreSQL backup and recovery. It supports both SSH-based backups to a dedicated backup server and S3-compatible object storage. The role handles client and server configuration, SSH key distribution, backup user creation, initial backup, and automated backup scheduling.

## Purpose

- Configure pgBackRest on PostgreSQL nodes (clients)
- Configure pgBackRest on dedicated backup servers
- Set up SSH authentication for backup access
- Create backup database user
- Configure PostgreSQL archive command
- Integrate with Patroni for HA clusters
- Take initial bootstrap backup
- Schedule automated full and differential backups
- Support both SSH and S3 backup repositories

## Role Dependencies

- `role_config` - Provides shared configuration variables
- `install_backrest` - pgBackRest must be installed
- `setup_postgres` - PostgreSQL must be configured
- `init_server` - SSH keys must be generated

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

This role is designed for idempotency:

- Configuration file is regenerated each run
- SSH key distribution is idempotent
- Backup user creation is idempotent
- Initial backup is skipped if repository exists
- Cron job creation is idempotent

## Troubleshooting

### Initial Backup Fails

**Symptom:** stanza-create or initial backup fails

**Solution:**

- Verify PostgreSQL is running
- Check pgBackRest configuration:

```bash
sudo -u postgres pgbackrest info
```

- Test backup command manually:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 check
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 backup --type=full
```

- Check logs:

```bash
sudo tail -f /var/log/pgbackrest/*
```

### SSH Connection Fails

**Symptom:** Cannot connect to backup server via SSH

**Solution:**

- Test SSH connectivity:

```bash
sudo -u postgres ssh backup-server
```

- Verify SSH keys:

```bash
sudo -u postgres ls -la ~/.ssh/
```

- Check authorized_keys on backup server
- Verify firewall allows SSH (port 22)

### S3 Connection Fails

**Symptom:** Cannot connect to S3 repository

**Solution:**

- Verify S3 credentials are correct
- Test S3 access:

```bash
aws s3 ls s3://bucket-name --region us-west-2
```

- Check network connectivity to S3 endpoint
- Verify bucket exists and is accessible
- Check IAM permissions for backup operations

### Archive Command Fails

**Symptom:** WAL archiving errors in PostgreSQL logs

**Solution:**

- Check PostgreSQL logs:

```bash
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

- Test archive command manually:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 archive-push /path/to/wal/file
```

- Verify backup repository is accessible
- Check pgBackRest configuration
- Ensure initial backup completed successfully

### Backup User Cannot Connect

**Symptom:** Backup user authentication fails

**Solution:**

- Verify backup user exists:

```bash
sudo -u postgres psql -c "\du backrest"
```

- Check pg_hba.conf allows connections:

```bash
sudo -u postgres grep backrest /var/lib/pgsql/17/data/pg_hba.conf
```

- Test connection manually:

```bash
psql -h localhost -U backrest -d postgres
```

- Verify `.pgpass` file has correct password

### Cron Jobs Not Running

**Symptom:** Automated backups not executing

**Solution:**

- Check crontab:

```bash
sudo -u postgres crontab -l
```

- Verify cron service is running:

```bash
sudo systemctl status cron  # Debian
sudo systemctl status crond  # RHEL
```

- Check cron logs:

```bash
sudo grep pgbackrest /var/log/cron
sudo tail -f /var/log/pgbackrest/*
```

- Test backup command manually

### Repository Full

**Symptom:** Backups fail due to insufficient space

**Solution:**

- Check repository disk space:

```bash
df -h /home/backrest
```

- Review retention settings (increase retention may fill disk)
- Manually expire old backups:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 expire
```

- Consider increasing disk space or reducing retention

### Backup Encryption Issues

**Symptom:** Cannot restore encrypted backup

**Solution:**

- Verify cipher passphrase is correct in configuration
- Ensure cipher passphrase is consistent across all nodes
- Check `backup_repo_cipher` variable matches original
- Note: Losing encryption key makes backups unrecoverable

### Standby Backup Fails

**Symptom:** Backups fail when run from replica

**Solution:**

- pgBackRest should run from primary in HA clusters
- Verify `inventory_hostname == first_node_in_zone` logic
- Check Patroni cluster status:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yaml list
```

- Ensure cron jobs only run on primary node

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

## See Also

- [install_backrest](install_backrest.md) - Required prerequisite for pgBackRest installation
- [setup_postgres](setup_postgres.md) - PostgreSQL setup before backup configuration
- [init_server](init_server.md) - Generates SSH keys used for backup authentication
- [Configuration Reference](../configuration.md) - Backup configuration variables
