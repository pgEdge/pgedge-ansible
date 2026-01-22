# Solving Backup and Recovery Issues

Reliable backup and recovery procedures are essential for protecting pgEdge
cluster data and enabling efficient restoration during failures. Backup issues
typically manifest as connection failures to backup servers, authentication
problems, or repository access errors that prevent successful backup
operations.

Troubleshooting these issues requires verification of SSH connectivity, S3
access permissions, and proper Postgres authentication for backup users. This
section covers comprehensive solutions for backup-related problems that could
impact your ability to restore data when needed.

For problems not covered by this guide, please refer to the 
[PgBackRest command reference](https://pgbackrest.org/command.html).

## Initial Backup Fails

Initial backup failures occur during stanza creation or the first full backup
operation.

**Symptom:** The stanza-create command or initial backup fails with a 
configuration or connection error.

**Solution:**

Ensure that Postgres runs on the target host. Check the pgBackRest
configuration status:

```bash
sudo -u postgres pgbackrest info
```

Test the backup configuration and connectivity:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 check
```

Attempt a manual full backup to capture detailed error messages:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 backup --type=full
```

Review the pgBackRest logs for detailed error information:

```bash
sudo tail -f /var/log/pgbackrest/*
```

## SSH Connection Fails

SSH connection failures prevent pgBackRest from communicating with remote
backup servers.

**Symptom:** PgBackRest cannot connect to the backup server via SSH.

**Solution:**

Test SSH connectivity from the Postgres host to the backup server:

```bash
sudo -u postgres ssh backup-server
```

Verify that the SSH keys exist and have correct permissions:

```bash
sudo -u postgres ls -la ~/.ssh/
```

- Check that the `authorized_keys` file on the backup server contains the
  correct public key.
- Verify that the firewall allows SSH traffic on port 22.

## S3 Connection Fails

S3 connection failures prevent pgBackRest from storing or retrieving backups in
cloud storage.

**Symptom:** PgBackRest cannot connect to the S3 backup repository.

**Solution:**

Ensure that the pgBackRest configuration contains correct S3 credentials. Test
S3 access using the AWS CLI:

```bash
aws s3 ls s3://bucket-name --region us-west-2
```

- Verify network connectivity from the host to the S3 endpoint.
- Confirm that the bucket exists and the configured credentials can access the
  bucket.
- Check IAM permissions to ensure they allow the required backup operations.

## Archive Command Fails

WAL archiving failures prevent Postgres from shipping transaction logs to the
backup repository.

**Symptom:** Postgres logs display WAL archiving errors or archive command failures.

**Solution:**

Check the Postgres logs for archive-related errors:

```bash
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

Test the archive command manually to verify functionality:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 archive-push /path/to/wal/file
```

- Verify that pgBackRest can access the backup repository.
- Review the pgBackRest configuration for archive settings.
- Ensure that the initial backup completed successfully before archiving.

## Backup User Cannot Connect

Authentication failures for the backup user prevent pgBackRest from accessing
Postgres.

**Symptom:** The backup user fails to authenticate when connecting to Postgres.

**Solution:**

Confirm that the backup user exists in Postgres:

```bash
sudo -u postgres psql -c "\du backrest"
```

- Check that `pg_hba.conf` includes an entry for the backup user.
- Verify that the pgBackRest configuration contains the correct backup user
  password.
- Test the connection manually from the backup server to confirm
  authentication.
