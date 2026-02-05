# Backup Configuration

The pgEdge Ansible collection provides pgBackRest as the default backup
management software. The following settings control how backup functionality
behaves. The `install_backrest` and `setup_backrest` roles use these variables.

## backup_repo_type

- Type: String
- Default: `ssh`
- Options: `ssh`, `s3`
- Description: This parameter specifies the PgBackRest repository type.

    - The `ssh` value requires a dedicated backup server in the `backup` group.
    - The `s3` value uses AWS S3 or compatible object storage.

In the following example, the inventory specifies SSH-based backups:

```yaml
backup_repo_type: ssh
```

## backup_host

- Type: String
- Default: The collection selects the first node in the `backup` group within
  the same zone.
- Description: This parameter specifies the hostname of the backup server when
  using SSH mode.

In the following example, the inventory specifies the backup server hostname:

```yaml
backup_host: backup1.example.com
```

## backup_repo_user

- Type: String
- Default: `{{ ansible_user_id }}`
- Description: This parameter specifies the OS user that owns the PgBackRest
  repository when using SSH mode.

In the following example, the inventory specifies the repository owner:

```yaml
backup_repo_user: backrest
```

## backup_repo_path

- Type: String
- Default: `/home/backrest`
- Description: This parameter specifies the full path to the PgBackRest
  repository storage location.

In the following example, the inventory specifies a custom repository path:

```yaml
backup_repo_path: /backup/pgbackrest
```

## backup_user

- Type: String
- Default: `backrest`
- Description: This parameter specifies the database username for backups when
  using SSH mode.

In the following example, the inventory specifies the backup database user:

```yaml
backup_user: backrest
```

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
  files.

In the following example, the inventory specifies the encryption algorithm:

```yaml
backup_repo_cipher_type: aes-256-cbc
```

## backup_repo_cipher

- Type: String
- Default: Auto-generated from cluster name.
- Description: This parameter specifies the encryption cipher for backup files.
  The roles generate a deterministic random string when you do not specify this
  parameter.

!!! warning "Important"
    Store this value securely. Lost ciphers make backups unrecoverable.

In the following example, the inventory retrieves the cipher from Ansible
Vault:

```yaml
backup_repo_cipher: "{{ vault_backup_cipher }}"
```

## full_backup_count

- Type: Integer
- Default: `1`
- Description: This parameter specifies the number of full backups to retain.

In the following example, the inventory retains two full backups:

```yaml
full_backup_count: 2
```

## diff_backup_count

- Type: Integer
- Default: `6`
- Description: This parameter specifies the number of differential backups to
  retain.

In the following example, the inventory retains seven differential backups:

```yaml
diff_backup_count: 7
```

## full_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 0` (Sundays at 00:10)
- Description: This parameter specifies the cron schedule for automated full
  backups.

In the following example, the inventory schedules full backups for Sunday at
2:00 AM:

```yaml
full_backup_schedule: "0 2 * * 0"  # Sundays at 2:00 AM
```

## diff_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 1-6` (Monday-Saturday at 00:10)
- Description: This parameter specifies the cron schedule for automated
  differential backups.

In the following example, the inventory schedules differential backups for
Monday through Saturday at 2:00 AM:

```yaml
diff_backup_schedule: "0 2 * * 1-6"  # Mon-Sat at 2:00 AM
```

## backup_repo_params

- Type: Dictionary
- Default:

    ```yaml
    backup_repo_params:
      region: us-east-1
      endpoint: s3.amazonaws.com
      bucket: pgbackrest
      access_key: ''
      secret_key: ''
    ```

- Description: This parameter provides configuration for S3 backup
  repositories. You must specify this parameter when you set the
  `backup_repo_type` parameter to `s3`.

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
