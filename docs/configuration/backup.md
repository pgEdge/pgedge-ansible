# Backup Configuration

The pgEdge Ansible Collection uses PgBackRest for backup management. The
following parameters control how backup functionality behaves. The
`install_backrest` and `setup_backrest` roles use these variables.

## backup_repo_type

- Type: String
- Default: `ssh`
- Options: `ssh`, `s3`
- Description: This parameter specifies the PgBackRest repository type.
  Using `ssh` requires a dedicated backup server in the `backup` host group.
  Using `s3` stores backups in AWS S3 or compatible object storage.

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
- Default: Ansible user
- Description: This parameter specifies the OS user that owns the PgBackRest
  repository on the backup server in SSH mode.

In the following example, the inventory specifies the repository owner:

```yaml
backup_repo_user: backrest
```

## backup_repo_path

- Type: String
- Default: `/home/backrest`
- Description: This parameter specifies the full path to the PgBackRest
  repository storage location. For S3 repositories, use a simple path such
  as `/backrest`.

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
- Description: This parameter specifies the encryption algorithm for backup
  files stored in the PgBackRest repository.

## backup_repo_cipher

- Type: String
- Default: (generated)
- Description: This parameter specifies the encryption cipher for backup files.
  When unset, the collection generates a 20-character deterministic random
  string based on the repository name and zone.

!!! warning "Important"
    Store this value securely. A lost cipher makes backups unrecoverable.

In the following example, the inventory retrieves the cipher from Ansible
Vault:

```yaml
backup_repo_cipher: "{{ vault_backup_cipher }}"
```

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

## backup_repo_params

- Type: Dictionary
- Default: See below.
- Description: This parameter provides configuration for S3 backup
  repositories. You must specify this parameter when you set `backup_repo_type`
  to `s3`.

The `backup_repo_params` dictionary accepts the following keys with the
defaults shown:

```yaml
backup_repo_params:
  region: us-east-1
  endpoint: s3.amazonaws.com
  bucket: pgbackrest
  access_key: ''
  secret_key: ''
```

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
