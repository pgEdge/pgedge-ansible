# setup_backrest

The `setup_backrest` role configures PgBackRest for Postgres backup and
recovery. The role supports both SSH-based backups to a dedicated backup server
and S3-compatible object storage. It handles configuration file generation, SSH
key distribution, backup user creation, WAL archiving, and automated scheduling.

The role performs the following tasks on inventory hosts:

- Create the `backup_user` PostgreSQL role with `pg_checkpoint` privileges and
  configure `pg_hba.conf` to allow backup connections.
- Generate `pgbackrest.conf` from a template, configuring the repository type,
  path, encryption, and retention settings.
- For SSH repositories, configure SSH access between the pgEdge node and the
  backup server using the `postgres` OS user.
- Configure PostgreSQL to archive WAL files to the PgBackRest repository and
  to retrieve WAL files from the repository during recovery.
- Initialize the backup repository stanza for each zone.
- Run the first backup to bootstrap the repository.
- Create cron entries for scheduled full and differential backups.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_backrest` installs PgBackRest packages on inventory hosts.
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
    - install_repos
    - install_backrest
    - setup_backrest
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `backup_repo_type` | Repository type: `ssh` or `s3` (default: `ssh`). |
| `backup_repo_path` | Repository path for backup storage. |
| `backup_repo_user` | OS user for backup operations. |
| `backup_repo_cipher_type` | Encryption algorithm (default: `aes-256-cbc`). |
| `backup_repo_cipher` | Encryption key; auto-generated from cluster settings if unset. |
| `backup_host` | Backup server hostname; auto-detected from the `backup` group. |
| `backup_user` | Backup database user (default: `backrest`). |
| `backup_password` | Password for the backup database user. |
| `full_backup_count` | Number of full backups to retain. |
| `diff_backup_count` | Number of differential backups to retain. |
| `full_backup_schedule` | Cron schedule for full backups. |
| `diff_backup_schedule` | Cron schedule for differential backups. |
| `backup_repo_params` | Dictionary with S3 parameters for S3-based backups. |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

The role adapts its operation based on whether the target host is a Postgres
node or a dedicated backup server.

### Client Configuration (Postgres Nodes)

When the role runs on pgedge hosts, it performs the following steps:

1. Generate `/etc/pgbackrest/pgbackrest.conf` with stanza settings and
   repository connection details based on `backup_repo_type`.
2. For SSH mode, add the backup server SSH host key to `known_hosts` and
   distribute the `postgres` user's SSH public key to the backup server.
3. Configure the Postgres `archive_command` to use PgBackRest. For HA
   clusters, this is applied through Patroni DCS configuration.
4. Create the backup database user with `pg_checkpoint` privileges and add a
   `pg_hba.conf` entry for backup server connections.
5. Initialize the stanza and run the first full backup to verify the
   repository.
6. Create cron jobs for the postgres user to run scheduled full and
   differential backups.

### Server Configuration (Backup Nodes)

When the role runs on dedicated backup hosts, it performs the following steps:

1. Generate `pgbackrest.conf` with a multi-node stanza listing all Postgres
   nodes in the zone.
2. Authorize SSH keys from all Postgres nodes and create `.pgpass` for
   database connections.
3. Initialize the stanza and run the first full backup from the server side.
4. Create cron jobs for the backup repository user.

### S3 Repository Configuration

When `backup_repo_type` is `s3`, the role configures S3-specific settings
instead of SSH-based backups. S3 mode eliminates the need for a dedicated
backup server. The following example configures S3 backup parameters:

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

!!! important "Initial Backup Required"
    An initial full backup must complete successfully before automated backups
    or WAL archiving will work correctly.

## Usage Examples

In the following example, the playbook configures SSH-based backups to a
dedicated backup server:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    backup_repo_type: ssh
  roles:
    - setup_backrest

- hosts: backup
  collections:
    - pgedge.platform
  vars:
    backup_repo_path: /backups/pgedge
  roles:
    - install_backrest
    - setup_backrest
```

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

## Artifacts

This role generates and modifies the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/pgbackrest/pgbackrest.conf` | New | PgBackRest configuration file with stanza settings, repository configuration, and encryption parameters. |
| `~postgres/.ssh/known_hosts` | Modified | SSH host keys for backup server communication in SSH mode. |
| `~postgres/.pgpass` | Modified | Backup user credentials for automated authentication. |
| `{{ backup_repo_path }}/archive/` | New | WAL archive storage directory on the backup server or in S3. |
| `{{ backup_repo_path }}/backup/` | New | Backup file storage directory on the backup server or in S3. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role skips
backup user creation when the user already exists and preserves existing
PgBackRest stanzas. The role may regenerate configuration files and update
cron job schedules when parameters change.

!!! warning "Encryption Keys"
    The role auto-generates `backup_repo_cipher` based on cluster name and
    zone when the parameter is unset. Losing this key makes backups
    unrecoverable. Store the key securely.

!!! note "HA Cluster Integration"
    For HA clusters, this role integrates with Patroni to configure
    `archive_command` cluster-wide. Patroni may overwrite manual changes to
    `archive_command`.
