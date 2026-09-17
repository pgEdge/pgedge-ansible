# finalize_backrest

The `finalize_backrest` role initializes the PgBackRest repository and the backup
schedule for a cluster that is up and running. It creates the backup database
user, creates the repository stanza if it does not exist, takes a full backup if
the stanza holds none, and installs the cron entries for scheduled full and
differential backups.

It is the second half of backup setup. `setup_backrest` writes configuration and
needs nothing running, so it is applied before Patroni starts Postgres;
everything this role does needs a live cluster to talk to, so it is applied last.

The role performs the following tasks on inventory hosts:

- Compare the cluster's system identifier against the one the stanza describes,
  and stop if they disagree.
- Create the `backup_user` PostgreSQL role with `pg_checkpoint` privileges, and
  for non-HA clusters add the matching `pg_hba.conf` entries.
- Create the repository stanza when the repository does not already have one.
- For non-HA clusters, set the Postgres `archive_command` and `restore_command`
  to use PgBackRest. HA clusters get both from the Patroni configuration.
- Take an initial full backup when the stanza holds no backups.
- Create cron entries for scheduled full and differential backups.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_backrest` writes the PgBackRest configuration this role acts through.
- `setup_patroni` or `setup_postgres` leaves a running cluster for the stanza
  and the first backup to be taken against.

## When to Use

Apply this role at the very end of a deployment, after the cluster is wired
together, on both the pgEdge nodes and any dedicated backup servers:

```yaml
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
| `full_backup_schedule` | Cron schedule for full backups. |
| `diff_backup_schedule` | Cron schedule for differential backups. |
| `backup_user` | Backup database user (default: `backrest`). |
| `backup_password` | Password for the backup database user. |
| `backup_repo_type` | Decides whether the stanza and the first backup are driven from a pgEdge node or from the backup server. |
| `backup_repo_user` | OS user the backup server runs PgBackRest as. |

The two schedules are this role's own defaults, because it is the only role that
reads them. Everything else PgBackRest needs — the repository type, path,
encryption and retention — is rendered into `pgbackrest.conf` by
[`setup_backrest`](setup_backrest.md) and read from the file here. See the
[Backup Configuration](../configuration/backup.md) reference for descriptions
and defaults.

## How It Works

The role's one decision is whether to take a backup, and it asks the repository
rather than assuming. `pgbackrest info` reports what the stanza holds; the
stanza is created only when it does not exist, and a full backup is taken only
when the stanza holds none.

That matters because of retention. `full_backup_count` defaults to `1`, which
renders `repo1-retention-full=1`, so a full backup taken against a repository
that already has one expires the previous full backup and the WAL that belongs
to it the moment it completes. A deployment re-run against a cluster whose
repository has been collecting backups for months would otherwise discard the
recovery point it was holding. Because the decision is made from the
repository's contents rather than from where the role sits in a playbook, the
role is safe to apply at any point after the cluster is up.

In SSH mode the stanza and the first backup are driven from the dedicated backup
server, which is where the repository lives. In S3 mode there is no server, so
the zone's first pgEdge node drives them instead.

### Repository Identity

Before anything else, the role reads the system identifier from the node's
`pg_control` and compares it against the identifiers the stanza reports. A
mismatch means this cluster is not the one the repository holds backups for:
archiving would be refused, the scheduled backups would fail nightly, and the
repository's recovery point would stop advancing while continuing to look
healthy. The role stops instead.

An empty repository has no identity to compare, so a genuine first deployment
passes. A cluster rebuilt deliberately during a recovery matches too, because
the recovery playbook records it in the stanza's history with
`pgbackrest stanza-upgrade` first.

`setup_postgres` asks the same question earlier, before it initializes a data
directory, using the same task file in `role_config`. The two differ in what an
unreadable repository means: the early check only ever refuses, so it skips a
repository it cannot reach — an SSH repository is not reachable from a pgEdge
node until the backup server has authorized its key. This check gates a decision
to write, so an unreadable repository is fatal here. Concluding "no backups
here" from a repository that could not be read is how a good backup gets
expired.

## Artifacts

This role generates and modifies the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ backup_repo_path }}/archive/` | New | WAL archive storage, created by `stanza-create`. |
| `{{ backup_repo_path }}/backup/` | New | Backup storage, created by `stanza-create`. |
| Crontab for the repository user | Modified | Scheduled full and differential backup entries. |

## Idempotency

This role is idempotent and safe to re-run. It creates neither a stanza nor a
backup that already exists, and cron entries are replaced rather than
duplicated. Re-running it against a healthy cluster changes nothing in the
repository.
