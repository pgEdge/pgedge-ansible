# Backup Configuration

The pgEdge Ansible collection provides pgBackRest as the default backup management software. The following settings control how backup functionality behaves. The `install_backrest` and `setup_backrest` roles mainly use these variables.

## backup_repo_type

- Type: String
- Default: `ssh`
- Options: `ssh`, `s3`
- Description: This parameter specifies the PgBackRest repository type.

    - `ssh` - Dedicated backup server (requires `backup` host group)
    - `s3` - AWS S3 or compatible object storage

```yaml
backup_repo_type: ssh
```

## backup_host

- Type: String
- Default: First node in `backup` group in the same zone
- Description: This parameter specifies the hostname of the backup server for SSH mode.

```yaml
backup_host: backup1.example.com
```

## backup_repo_user

- Type: String
- Default: `{{ ansible_user_id }}`
- Description: This parameter specifies the OS user that owns the PgBackRest repository (SSH mode only).

```yaml
backup_repo_user: backrest
```

## backup_repo_path

- Type: String
- Default: `/home/backrest`
- Description: This parameter specifies the full path to the PgBackRest repository storage location.

```yaml
backup_repo_path: /backup/pgbackrest
```

## backup_user

- Type: String
- Default: `backrest`
- Description: This parameter specifies the database username for backups (SSH mode only).

```yaml
backup_user: backrest
```

## backup_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the backup database user.

```yaml
backup_password: "{{ vault_backup_password }}"
```

## backup_repo_cipher_type

- Type: String
- Default: `aes-256-cbc`
- Description: This parameter specifies the encryption algorithm for backup files.

```yaml
backup_repo_cipher_type: aes-256-cbc
```

## backup_repo_cipher

- Type: String
- Default: Auto-generated from cluster name
- Description: This parameter specifies the encryption cipher for backup files. The roles generate a deterministic random string when you do not specify this parameter.

!!! warning "Important"
    Store this value securely. Lost ciphers make backups unrecoverable.

```yaml
backup_repo_cipher: "{{ vault_backup_cipher }}"
```

## full_backup_count

- Type: Integer
- Default: `1`
- Description: This parameter specifies the number of full backups to retain.

```yaml
full_backup_count: 2
```

## diff_backup_count

- Type: Integer
- Default: `6`
- Description: This parameter specifies the number of differential backups to retain.

```yaml
diff_backup_count: 7
```

## full_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 0` (Sundays at 00:10)
- Description: This parameter specifies the cron schedule for automated full backups.

```yaml
full_backup_schedule: "0 2 * * 0"  # Sundays at 2:00 AM
```

## diff_backup_schedule

- Type: String (cron format)
- Default: `10 0 * * 1-6` (Monday-Saturday at 00:10)
- Description: This parameter specifies the cron schedule for automated differential backups.

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

- Description: This parameter provides configuration for S3 backup repositories. You must specify this parameter when you set the `backup_repo_type` parameter to `s3`.

```yaml
backup_repo_params:
  region: us-west-2
  endpoint: s3.amazonaws.com
  bucket: my-pg-backups
  access_key: "{{ vault_aws_access_key }}"
  secret_key: "{{ vault_aws_secret_key }}"
```
