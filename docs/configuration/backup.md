# Backup Configuration

The pgEdge Ansible Collection uses PgBackRest for backup management. The
following parameters control how backup functionality behaves. The
`install_backrest`, `setup_backrest`, `finalize_backrest` and `recover_postgres`
roles use these variables.

## backup_repo_type

- Type: String
- Default: `ssh`
- Options: `ssh`, `s3`
- Description: This parameter specifies the PgBackRest repository type.
  Using `ssh` requires a dedicated backup server in the `backup` host group.
  Using `s3` stores backups in AWS S3 or compatible object storage, and
  needs no backup server: a zone that uses `s3` must not have a host in the
  `backup` group, and `init_server` refuses one that does.

In the following example, the inventory specifies SSH-based backups:

```yaml
backup_repo_type: ssh
```

## backup_host

- Type: String
- Default: (none - first node in the `backup` group in the same zone)
- Description: This parameter specifies the hostname of the backup server when
  using SSH mode. When empty, the collection selects the first node in the
  `backup` host group that shares the same zone as the Postgres node.

In the following example, the inventory specifies the backup server hostname:

```yaml
backup_host: backup1.example.com
```

## backup_repo_user

- Type: String
- Default: the account Ansible logs in as — `ansible_user` where the
  inventory or `remote_user` names one, falling back to the `ansible_user_id`
  fact where neither does
- Description: This parameter specifies the OS user that owns the PgBackRest
  repository on the backup server in SSH mode.

In the following example, the inventory specifies the repository owner:

```yaml
backup_repo_user: backrest
```

## backup_repo_path

- Type: String
- Default: the home directory of the account Ansible logs in as, such as
  `/home/ansible`
- Description: This parameter specifies the full path to the PgBackRest
  repository storage location. For S3 repositories, use a simple path such
  as `/backrest`.

!!! note "Setting `backup_repo_user` does not move the path"
    The two default independently: `backup_repo_user` names the account that
    owns the repository, and this names where the repository lives. Giving the
    repository a dedicated owner without also setting this parameter leaves it
    in the login user's home directory. Set both together.

In the following example, the inventory specifies a custom repository path:

```yaml
backup_repo_path: /backup/pgbackrest
```

## backup_user

- Type: String
- Default: `backrest`
- Description: This parameter specifies the PostgreSQL username for backup
  operations. The collection creates this user with `pg_checkpoint` privileges.

## backup_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the backup database
  user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
backup_password: "{{ vault_backup_password }}"
```

## backup_repo_cipher_type

- Type: String
- Default: `aes-256-cbc`
- Options: `aes-256-cbc`, `none`
- Description: This parameter specifies the encryption algorithm PgBackRest
  applies to the repository. Set it to `none` where the storage layer encrypts
  instead.

## backup_repo_cipher

- Type: String
- Default: (none — you must set it)
- Description: This parameter specifies the password PgBackRest encrypts the
  repository with. It is required whenever `backup_repo_cipher_type` is not
  `none`, and rejected when it is.

```yaml
backup_repo_cipher: "{{ vault_backup_cipher }}"
```

!!! warning "Store it, and do not change it"
    A lost cipher is an unreadable repository, and PgBackRest cannot rotate it.
    Changing this on a cluster with existing backups makes those backups
    unreadable.

### Why there is no default

This parameter cannot be defaulted into existence. A generated value would have
to satisfy two requirements at once that nothing can meet together:

- **Identical on every run.** A repository whose cipher changed between runs is
  a repository that can no longer be read, so the value cannot be random.
- **Not guessable.** Anyone who can read the repository and knows the password
  can read the backups.

Earlier releases resolved that by deriving the value from `cluster_name` and
`zone`, which met the first requirement by abandoning the second: both are
public, so the password was reproducible by anyone who knew the cluster's name.
Only a secret you keep can be both, so `init_server` now requires one.

### Relying on storage-layer encryption instead

Encrypting at the storage layer is a legitimate arrangement, and the only one
that permits key rotation — PgBackRest cannot rotate its own cipher, whereas
S3 bucket default encryption and SSE-KMS can rotate underneath an unchanged
repository. To use it, turn PgBackRest's own encryption off and supply no
password:

```yaml
backup_repo_type: s3
backup_repo_cipher_type: none
```

The repository configuration then carries `repo1-cipher-type=none` and no
password line at all, which is what PgBackRest requires — it rejects a
configuration that names a password while encrypting nothing.

### Upgrading a cluster deployed before this was required

Its repository is encrypted with the old derived password, and that derivation
was public, so the value can be recovered and then set explicitly. Substitute
the cluster's own `cluster_name` and `zone`:

```bash
ansible localhost -m debug \
  -a "msg={{ lookup('password', '/dev/null', length=20, seed='pgedgedemo-1') }}"
```

The seed is the literal string `pgedge`, the cluster name, a hyphen, and the
zone — so `pgedge` + `demo` + `-` + `1` for a cluster named `demo` in zone 1.
Each zone has its own repository and therefore its own password. Put the
results in Ansible Vault and set `backup_repo_cipher` from there.

!!! danger "Treat those values as compromised"
    A password anyone could derive is not a secret. Recovering it is how you
    keep reading the existing repository, not a state to stay in. Plan to
    re-encrypt: take a fresh full backup under a new password into a new
    repository, or move to storage-layer encryption, and retire the old
    repository once its retention has passed.

## full_backup_count

- Type: Integer
- Default: `1`
- Description: This parameter specifies the number of full backups to retain
  in the repository.

## diff_backup_count

- Type: Integer
- Default: `6`
- Description: This parameter specifies the number of differential backups
  to retain in the repository.

## full_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 0` (Sundays at 00:10 UTC)
- Description: This parameter specifies the cron schedule for automated full
  backups.

In the following example, the inventory schedules full backups for Sunday at
2:00 AM:

```yaml
full_backup_schedule: "0 2 * * 0"
```

## diff_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 1-6` (Monday through Saturday at 00:10 UTC)
- Description: This parameter specifies the cron schedule for automated
  differential backups.

In the following example, the inventory schedules differential backups for
Monday through Saturday at 2:00 AM:

```yaml
diff_backup_schedule: "0 2 * * 1-6"
```

### Turning off scheduled backups

To leave the scheduling to something else, set either schedule to an empty
string. The collection installs a cron entry only for a schedule with exactly
five fields, so an empty value installs no entry:

```yaml
full_backup_schedule: ""
diff_backup_schedule: ""
```

This has no effect on the first full backup the deployment takes; only the
recurring jobs are left out.

!!! note "An existing entry is left in place"
    An empty schedule tells the collection not to install an entry; it does
    not remove one. A host deployed earlier with a schedule keeps its
    `Full PgBackRest schedule` and `Differential PgBackRest schedule` entries
    in the crontab of the user that runs PgBackRest, so remove them yourself
    with `crontab -e`.

## backup_repo_params

- Type: Dictionary
- Default: See below.
- Description: This parameter provides configuration for S3 backup
  repositories. You must specify this parameter when you set `backup_repo_type`
  to `s3`. The dictionary is merged over the defaults below, so an inventory
  names only the keys it changes. `init_server` refuses an S3 configuration
  with an empty `access_key`, `secret_key`, `bucket`, `region` or `endpoint`.

The `backup_repo_params` dictionary accepts the following keys with the
defaults shown:

```yaml
backup_repo_params:
  region: us-east-1
  endpoint: s3.amazonaws.com
  bucket: pgbackrest
  access_key: ''
  secret_key: ''
  uri_style: ''
  storage_ca_file: ''
  storage_port: ''
  storage_verify_tls: ''
```

- `uri_style` sets PgBackRest's `repo1-s3-uri-style`: `host` addresses the
  bucket as `bucket.endpoint`, and `path` as `endpoint/bucket`. Left empty, the
  setting is omitted and PgBackRest uses `host`, which is what AWS S3 expects.
  S3-compatible stores such as MinIO usually need `path`.
- `storage_ca_file` sets PgBackRest's `repo1-storage-ca-file`, the certificate
  authority that verifies the endpoint's TLS certificate. Left empty, the
  setting is omitted and PgBackRest uses the system CA bundle. Set it when the
  endpoint's certificate comes from a private authority. It is a path on the
  pgEdge nodes, and the collection does not copy the file there.
- `storage_port` sets PgBackRest's `repo1-storage-port`. Left empty, the setting
  is omitted and PgBackRest connects on 443. MinIO listens on 9000 by default.
- `storage_verify_tls` sets PgBackRest's `repo1-storage-verify-tls`, as `y` for
  `true` and `n` for `false`. Left empty, the setting is omitted and PgBackRest
  verifies the endpoint's certificate. Setting it to `false` accepts any
  certificate at all, so reserve it for test environments and prefer
  `storage_ca_file` for a privately signed certificate.

In the following example, the inventory configures S3 backup storage with
credentials from Ansible Vault:

```yaml
backup_repo_params:
  region: us-west-2
  endpoint: s3.amazonaws.com
  bucket: my-pg-backups
  access_key: "{{ vault_aws_access_key }}"
  secret_key: "{{ vault_aws_secret_key }}"
```

In the following example, the inventory configures a MinIO server listening on
its default port, whose certificate is signed by a private authority:

```yaml
backup_repo_params:
  endpoint: minio.example.com
  bucket: pg-backups
  access_key: "{{ vault_minio_access_key }}"
  secret_key: "{{ vault_minio_secret_key }}"
  uri_style: path
  storage_port: 9000
  storage_ca_file: /etc/pki/tls/certs/minio-ca.crt
```

## patroni_replica_from_backup

- Type: Boolean
- Default: `false`
- Description: This parameter controls whether Patroni rebuilds a replica from
  the backup repository instead of streaming a fresh `pg_basebackup` from its
  zone's leader. When enabled, Patroni tries a PgBackRest delta restore first
  and falls back to `pg_basebackup` if it fails.

A delta restore moves only the blocks that changed and reads from the
repository rather than from the leader, which is worth it for a large database.
It also makes replica creation depend on the repository being healthy, so it is
off by default; a cluster that leaves it unset builds replicas exactly as it
did before.

In the following example, the inventory rebuilds replicas from the repository:

```yaml
patroni_replica_from_backup: true
```

## Recovery Parameters

The following parameters apply only to the
[`recover_postgres`](../roles/recover_postgres.md) role, which the recovery
playbook described in [Recovering a Cluster from Backup](../recovery.md) uses.
They are all empty by default, and an ordinary deployment never reads them.

Pass them on the `ansible-playbook` command line rather than writing them into
an inventory, where they would sit waiting for the next unrelated run.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `recovery_node` | (none) | The pgEdge node to restore from its repository, spelled as the inventory spells it. Must be the first node of its zone. |
| `recovery_target_type` | (none) | PgBackRest `--type`: `time`, `xid`, `lsn`, `name` or `immediate`. Unset restores everything the repository holds. |
| `recovery_target` | (none) | The value the target type stops at. Required for `time`, `xid`, `lsn` and `name`; must be unset for `immediate` or no type. |
| `recovery_target_timeline` | (none) | PgBackRest `--target-timeline`. Unset follows the newest timeline. |
| `recovery_backup_set` | (none) | A specific backup to restore, labelled as `pgbackrest info` labels it. Unset takes the newest backup that can reach the target. |
| `recovery_stall_minutes` | `15` | Give up only after the restored node has made no progress for this long. |
| `recovery_poll_seconds` | `30` | How often to look. |
| `recovery_max_hours` | `24` | Hard ceiling on the restore, the replay, and each zone's Spock copy. |

In the following example, the command restores a wiped cluster to a point in
time:

```bash
ansible-playbook -i inventory.yaml playbook.yaml \
  -e recovery_node=192.168.6.10 \
  -e recovery_target_type=time \
  -e "recovery_target='2026-09-15 14:30:00+00'"
```

!!! note "Recovery never removes a backup"
    The recovery takes no backup and leaves the schedule off, so it can be
    repeated until the result is right. Committing it with
    `commit-restore.yaml` takes the backups it did not, and under the default
    retention expires the ones it came from.
