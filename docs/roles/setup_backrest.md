# setup_backrest

The `setup_backrest` role writes the PgBackRest configuration for a cluster. The
role supports both SSH-based backups to a dedicated backup server and
S3-compatible object storage, and handles configuration file generation and SSH
key distribution.

Nothing this role does touches Postgres, which is what lets it be applied before
Postgres exists. Two things depend on that. An HA cluster gets its archive
command from the Patroni configuration, so Postgres begins archiving the moment
Patroni starts it, and a `pgbackrest.conf` written after that point leaves a
window in which every archive attempt fails. And `setup_postgres` asks the
repository whether it already holds a cluster before it initializes a data
directory, which it can only do once `pgbackrest.conf` names the repository.

The steps that do need a live cluster — the backup database user, a non-HA
cluster's archive commands, the repository stanza, the first backup, and the
backup schedule — belong to [`finalize_backrest`](finalize_backrest.md), which is
applied at the end of a deployment.

The role performs the following tasks on inventory hosts:

- Generate `pgbackrest.conf` from a template, configuring the repository type,
  path, encryption, and retention settings.
- For SSH repositories, configure SSH access between the pgEdge node and the
  backup server using the `postgres` OS user.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_backrest` installs PgBackRest packages on inventory hosts.
- `setup_postgres` initializes and configures Postgres instances.
- `init_server` generates SSH keys for secure communication.

## When to Use

Execute this role on all pgedge hosts after `install_backrest` and **before**
`setup_postgres`, and on backup servers once the cluster's nodes exist.

In the following example, the playbook invokes the role on Postgres nodes and
a dedicated backup server:

```yaml
# Configure backups on Postgres nodes, before Postgres is initialized
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_backrest
    - setup_backrest
    - setup_postgres
    - setup_patroni

# Configure dedicated backup server
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
    - setup_backrest

# Initialize the repository once the cluster is up
- hosts: pgedge:backup
  collections:
    - pgedge.platform
  roles:
    - finalize_backrest
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
| `backup_repo_params` | Dictionary with S3 parameters for S3-based backups. |

The backup schedule is not here. `full_backup_schedule` and
`diff_backup_schedule` belong to [`finalize_backrest`](finalize_backrest.md),
which installs the cron entries.

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
The archive commands are not set here. An HA cluster gets them from the Patroni
configuration template, which is the only place they can live and survive a
recovery — a value patched into the Patroni configuration store is lost when the
cluster is removed from the store and bootstrapped again. A non-HA cluster gets
them from [`finalize_backrest`](finalize_backrest.md), which runs when Postgres is up to
be reloaded.

Client configuration is gated on a repository being configured at all, not on a
backup server being named. An S3 repository names no server, which is the point
of it.

### Server Configuration (Backup Nodes)

When the role runs on dedicated backup hosts, it performs the following steps:

1. Generate `pgbackrest.conf` with a multi-node stanza listing all Postgres
   nodes in the zone.
2. Authorize SSH keys from all Postgres nodes and create `.pgpass` for
   database connections.

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
    [`finalize_backrest`](finalize_backrest.md) takes it.

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
    - finalize_backrest

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
and backup schedules. Retention is rendered into `pgbackrest.conf` by this role;
the schedules are installed by [`finalize_backrest`](finalize_backrest.md), so both roles
need the variables:

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
    - finalize_backrest
```

Retention is rendered into `pgbackrest.conf` by this role and the schedule is
installed by `finalize_backrest`, but both read the values from the inventory,
so setting them there reaches whichever role wants them.

## Artifacts

This role generates and modifies the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/pgbackrest/pgbackrest.conf` | New | PgBackRest configuration file with stanza settings, repository configuration, and encryption parameters. |
| `~postgres/.ssh/known_hosts` | Modified | SSH host keys for backup server communication in SSH mode. |
| `~postgres/.pgpass` | Modified | Backup user credentials for automated authentication. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. It writes
configuration files and SSH trust and touches nothing in the repository.

!!! warning "Encryption Keys"
    The role auto-generates `backup_repo_cipher` based on cluster name and
    zone when the parameter is unset. Losing this key makes backups
    unrecoverable. Store the key securely.

!!! note "HA Cluster Integration"
    For an HA cluster, `archive_command` and `restore_command` come from
    `setup_patroni`'s configuration template rather than from this role.
    Patroni owns `postgresql.conf` on those nodes and overwrites manual changes
    to either setting.
