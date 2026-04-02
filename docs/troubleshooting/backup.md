# PgBackRest Issues

This page covers backup and recovery issues.

## Initial Backup Fails

**Symptom:** The stanza-create command or first full backup fails.

**Solution:** Verify that Postgres is running and test the backup
configuration:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 check
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 backup --type=full
```

Review the PgBackRest logs for details:

```bash
sudo tail -f /var/log/pgbackrest/*.log
```

## SSH Backup Connection Fails

**Symptom:** PgBackRest cannot connect to the backup server over SSH.

**Solution:** Test SSH connectivity as the `postgres` user:

```bash
sudo -u postgres ssh backup-server
```

Verify that the public key in `~postgres/.ssh/id_rsa.pub` on the Postgres
node appears in the `authorized_keys` file on the backup server.

## S3 Connection Fails

**Symptom:** PgBackRest cannot connect to the S3 backup repository.

**Solution:** Verify the S3 credentials and bucket access:

```bash
aws s3 ls s3://bucket-name --region us-west-2
```

Confirm network connectivity to the S3 endpoint and that the IAM policy
grants the required permissions.

## Backup User Cannot Authenticate

**Symptom:** The backup user fails to authenticate to Postgres.

**Solution:** Confirm that the backup user exists and has the correct
privileges:

```bash
sudo -u postgres psql -c "\du backrest"
```

Verify that `pg_hba.conf` includes an entry for the backup user and that the
`backup_password` in the inventory matches the user's password.
