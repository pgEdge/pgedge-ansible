# Postgres Issues

This page covers database initialization and startup issues.

## initdb Fails on RHEL

**Symptom:** The `postgresql-{{ pg_version }}-setup initdb` command fails.

**Solution:** Verify that the Postgres packages are installed. Check the
data directory permissions:

```bash
ls -la /var/lib/pgsql/17
```

Manually run initdb and review the output for errors:

```bash
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
```

## Service Won't Start

**Symptom:** The Postgres service fails to start after setup.

**Solution:** Check the Postgres logs for the root cause:

```bash
# Systemd journal
sudo journalctl -u postgresql-17 -n 50 --no-pager

# Debian log file
sudo tail -f /var/log/postgresql/postgresql-17-main.log

# RHEL log file
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

Check for port conflicts:

```bash
netstat -tnlp | grep 5432
```

## Extension Installation Fails

**Symptom:** The Spock or Snowflake extensions fail to install.

**Solution:** Verify that the pgEdge packages include the required extension
files:

```bash
ls -la /usr/pgsql-17/share/extension/spock*
ls -la /usr/pgsql-17/share/extension/snowflake*
```

Confirm that `shared_preload_libraries` lists the extensions and restart
Postgres after any configuration change.
