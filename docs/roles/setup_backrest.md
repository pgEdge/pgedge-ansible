# setup_backrest

The `setup_backrest` role configures pgBackRest for Postgres backup and
recovery. The role supports both SSH-based backups to a dedicated backup server
and S3-compatible object storage, handling client and server configuration,
SSH key distribution, backup user creation, and automated scheduling.

The role performs the following tasks on inventory hosts:

- Configure pgBackRest on Postgres nodes with appropriate repository settings.
- Set up SSH authentication for secure backup transfers between nodes.
- Create a backup database user with required replication privileges.
- Configure the Postgres archive command for WAL archiving.
- Integrate with Patroni for HA clusters to ensure consistent configuration.
- Take an initial bootstrap backup to verify repository functionality.
- Schedule automated full and differential backups via cron jobs.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_backrest` installs pgBackRest packages on inventory hosts.
- `setup_postgres` initializes and configures Postgres instances.
- `init_server` generates SSH keys for secure communication.

## When to Use

Execute this role on all pgedge hosts and backup servers after Postgres setup.

In the following example, the playbook invokes the role on Postgres nodes and
a dedicated backup server:

```yaml
# Configure backups on Postgres nodes
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

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    backup_repo_type: ssh
    backup_repo_path: /home/backrest
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `backup_repo_type` | Repository type: `ssh` or `s3` (default: `ssh`). |
| `backup_repo_path` | Repository path for backup storage. |
| `backup_repo_user` | OS user for backup operations. |
| `backup_repo_cipher_type` | Encryption algorithm (default: `aes-256-cbc`). |
| `backup_repo_cipher` | Encryption key (auto-generated from cluster settings). |
| `backup_host` | Backup server hostname (auto-detected from `backup` group). |
| `backup_user` | Backup database user (default: `backrest`). |
| `backup_password` | Password for the backup database user. |
| `full_backup_count` | Number of full backups to retain. |
| `diff_backup_count` | Number of differential backups to retain. |
| `full_backup_schedule` | Cron schedule for full backups. |
| `diff_backup_schedule` | Cron schedule for differential backups. |
| `backup_repo_params` | Dictionary with S3 parameters for S3-based backups. |

## How It Works

The role adapts its operation based on whether the target host is a
Postgres node or a dedicated backup server.

### Client Configuration

When the role runs on Postgres nodes, it performs these steps:

1. Generate the pgBackRest configuration file.
    - Create `/etc/pgbackrest/pgbackrest.conf` with stanza settings.
    - Configure repository connection details based on `backup_repo_type`.
    - Set encryption parameters for secure backup storage.

2. Configure SSH access for SSH-based backups.
    - Add the backup server SSH host key to `known_hosts`.
    - Distribute the postgres user SSH public key to the backup server.
    - Verify SSH connectivity for backup transfers.

3. Configure Postgres for archiving.
    - Set `archive_mode = on` in `postgresql.conf` for standalone clusters.
    - Update Patroni DCS configuration for HA clusters.
    - Configure `archive_command` to use pgBackRest.

4. Create the backup database user.
    - Create the backup user with REPLICATION privilege.
    - Add `pg_hba.conf` entry for backup server connections.
    - Create a `.pgpass` entry for automated authentication.

5. Take the initial backup.
    - Run stanza-create to initialize the repository.
    - Take an initial full backup to verify functionality.
    - Verify the backup repository is operational.

6. Schedule automated backups.
    - Create cron jobs for the postgres user.
    - Schedule full backups weekly (Sunday by default).
    - Schedule differential backups daily (Monday through Saturday).

### Server Configuration

When the role runs on dedicated backup servers, it performs these steps:

1. Generate the pgBackRest configuration file.
    - Create `/etc/pgbackrest/pgbackrest.conf` with multi-node stanza.
    - List all Postgres nodes in the zone for backup coordination.
    - Configure repository path and encryption settings.

2. Configure SSH access from Postgres nodes.
    - Authorize SSH keys from all Postgres nodes.
    - Add all Postgres nodes to `known_hosts`.
    - Create `.pgpass` for database connections during backup.

3. Take the initial backup.
    - Connect to the first node in the zone.
    - Run stanza-create and take a full backup.
    - Verify backup functionality from the server side.

4. Schedule automated backups.
    - Create cron jobs for the backup repository user.
    - Schedule full and differential backups from the backup server.

!!! important "Initial Backup Required"
    An initial full backup must complete successfully before automated backups
    or WAL archiving will work.

### S3 Repository Configuration

When the `backup_repo_type` parameter is `s3`, the role configures S3-specific
settings instead of SSH-based backups.

In the following example, the inventory configures S3 backup parameters:

```yaml
pgedge:
  vars:
    backup_repo_type: s3
    backup_repo_params:
      region: us-west-2
      endpoint: s3.amazonaws.com
      bucket: my-pg-backups
      access_key: "{{ vault_aws_access_key }}"
      secret_key: "{{ vault_aws_secret_key }}"
```

S3 mode eliminates the need for a dedicated backup server but requires cloud
access and credentials.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### SSH-Based Backups

In the following example, the playbook configures SSH-based backups to a
dedicated backup server:

```yaml
# Postgres nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    backup_repo_type: ssh
  roles:
    - setup_backrest

# Dedicated backup server
- hosts: backup
  collections:
    - pgedge.platform
  vars:
    backup_repo_path: /backups/pgedge
  roles:
    - install_backrest
    - setup_backrest
```

### S3-Based Backups

In the following example, the playbook configures S3-based backups without a
dedicated backup server:

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

In the following example, the playbook configures custom retention policies
and backup schedules:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    full_backup_count: 2
    diff_backup_count: 14
    full_backup_schedule: "0 2 * * 0"
    diff_backup_schedule: "0 2 * * 1-6"
  roles:
    - setup_backrest
```

### HA Cluster with Backups

In the following example, the playbook deploys an HA cluster with integrated
backup configuration:

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
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_backrest
    - setup_backrest
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/pgbackrest/pgbackrest.conf` | New | pgBackRest configuration file containing stanza settings, repository configuration, and encryption parameters. |
| `~postgres/.ssh/known_hosts` | Modified | SSH host keys for backup server communication in SSH mode. |
| `~postgres/.pgpass` | Modified | Backup user credentials for automated authentication. |
| `{{ backup_repo_path }}/archive/` | New | WAL archive storage directory on the backup server or S3 bucket. |
| `{{ backup_repo_path }}/backup/` | New | Backup file storage directory on the backup server or S3 bucket. |

## Platform-Specific Behavior

This role behaves identically on all supported platforms including Debian 12
and Rocky Linux 9.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Create the backup database user only when the user does not exist.
- Preserve existing pgBackRest stanza without overwriting.

The role may update these items on subsequent runs:

- Regenerate configuration files to incorporate inventory changes.
- Update cron job schedules when parameters change.

!!! warning "Encryption Keys"
    The `backup_repo_cipher` is auto-generated based on cluster name and zone.
    Losing this key makes backups unrecoverable; store the key securely.

!!! note "HA Cluster Integration"
    For HA clusters, this role integrates with Patroni to configure archiving
    cluster-wide; manual changes to archive_command may be overwritten.
