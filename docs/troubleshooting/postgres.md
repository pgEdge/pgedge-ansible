# Solving Postgres Issues

Postgres configuration represents the core of your pgEdge deployment, and
issues at this layer can completely prevent database operations. Problems range
from basic initialization failures during setup to advanced SSL configuration
challenges and extension management. Postgres service issues often manifest
as connection failures or service startup problems that leave your database
unavailable.

This section addresses Postgres-specific troubleshooting, covering everything
from initial database creation to SSL certificate generation, service
management, and extension installation challenges that can impact pgEdge's
functionality.

## initdb Fails on RHEL

**Symptom:** The `postgresql-{{ pg_version }}-setup initdb` command fails.

**Solution:**

- Verify that the system has the Postgres packages installed.

Check the data directory permissions with the following command:

```bash
ls -la /var/lib/pgsql/17
```

Manually initialize the database with the following command:

```bash
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
```

## SSL Certificate Generation Fails

**Symptom:** Ansible failes to create SSL certificates.

**Solution:**

Verify that the system has OpenSSL installed:

```bash
openssl version
```

- Check that the data directory permissions allow the `postgres` user to write.

Manually generate certificates with the following command:

```bash
sudo -u postgres openssl req -new -x509 -days 365 -nodes \
  -text -out /var/lib/pgsql/17/data/server.crt \
  -keyout /var/lib/pgsql/17/data/server.key \
  -subj "/CN=$(hostname)"
```

## Service Won't Start

**Symptom:** The Postgres service fails to start.

**Solution:**

Check the Postgres logs for error messages:

```bash
# Systemd
sudo journalctl -u postgresql-17 -f --no-pager

# Debian
sudo tail -f /var/log/postgresql/postgresql-17-main.log

# RHEL
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

Verify the configuration syntax with the following command:

```bash
sudo -u postgres /usr/pgsql-17/bin/postgres -D /var/lib/pgsql/17/data -C config_file
```

Check for port conflicts with the following command:

```bash
netstat -tnlp | grep 5432
```

## Extension Installation Fails

**Symptom:** The Spock or Snowflake extensions fail to install.

**Solution:**

Verify that the pgEdge packages include the required extensions:

```bash
# Check for extension files
ls -la /usr/pgsql-17/share/extension/spock*
ls -la /usr/pgsql-17/share/extension/snowflake*
```

- Check that `shared_preload_libraries` lists the required extensions.
- Restart Postgres after making configuration changes.

Manually test extension creation with the following command:

```bash
sudo -u postgres psql -c "CREATE EXTENSION spock CASCADE;"
```

## Connection Refused

**Symptom:** Cannot connect to Postgres after setup.

**Solution:**

- Verify that Postgres is running by executing `sudo systemctl status postgresql-17`.
- Check that Postgres listens on the correct port with `netstat -tnlp | grep 5432`.
- Verify that the firewall rules allow the Postgres port.
- Check that the `pg_hba.conf` file includes your connection source.
- Test a local connection by running `sudo -u postgres psql`.
