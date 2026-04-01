# Troubleshooting

This guide provides solutions to common issues encountered when deploying and
managing pgEdge clusters with the Ansible Collection.

## Collection Installation

This section covers issues that block cluster deployment before it begins.

### Collection Not Found

**Symptom:** Ansible reports that the `pgedge.platform` collection is not
found.

**Solution:** Verify that the collection installed correctly by running the
following command:

```bash
ansible-galaxy collection list pgedge.platform
```

If the collection is missing, reinstall it from the repository:

```bash
cd pgedge-ansible
make install
```

### Build Failure

**Symptom:** The `make install` command fails.

**Solution:** Ensure that Ansible and the `ansible-galaxy` command are
available on the control node. Check the `VERSION` file exists in the
repository root. If the file is missing, pull the latest changes with `git
pull` and retry.

### SSH Connection Failure

**Symptom:** Ansible cannot connect to target hosts.

**Solution:** Test connectivity from the control node to a target host:

```bash
ssh -i ~/.ssh/your_key user@target-host
ansible all -m ping -i inventory.yaml
```

Ensure that the target host accepts connections from the control node and
that the inventory specifies the correct `ansible_user` and SSH key.

## Package Repository

This section covers issues that prevent software installation.

### Repository Package Not Found

**Symptom:** Package installation fails with a "package not found" error
after `install_repos` runs.

**Solution:** Refresh the package cache and search for the package:

```bash
# Debian
sudo apt update && apt-cache search pgedge-enterprise

# RHEL
sudo dnf makecache && dnf search pgedge-enterprise
```

Verify that the correct repository configuration exists:

```bash
# Debian
cat /etc/apt/sources.list.d/pgedge.sources

# RHEL
cat /etc/yum.repos.d/pgedge.repo
```

### GPG Key Import Fails

**Symptom:** The repository key import task fails.

**Solution:** Verify network access to the pgEdge repository:

```bash
curl -s https://pgedge-downstream.s3.amazonaws.com/REPO/ubuntu/pgdg/jammy.pub
```

Check that the firewall allows HTTPS traffic and retry the `install_repos`
role.

### Lock Timeout on Debian

**Symptom:** A "Could not get lock" error occurs on Debian.

**Solution:** Check for other running apt processes:

```bash
ps aux | grep apt
```

The role uses a 300-second timeout. Wait for other package operations to
complete and retry.

## System Configuration

This section covers host-level configuration issues.

### SELinux Causes Service Failure

**Symptom:** Services fail on RHEL after deployment due to SELinux
denials.

**Solution:** Check SELinux audit logs for denials:

```bash
sudo ausearch -m AVC -ts recent
```

The `init_server` role sets `disable_selinux: true` by default. If you
changed this setting, review the audit logs and create the appropriate
SELinux policy. A system reboot may be required after disabling SELinux.

### SSH Key Problems

**Symptom:** PgBackRest SSH backup fails because of key authentication
errors.

**Solution:** Verify that the `postgres` OS user's SSH key exists and has
correct permissions:

```bash
sudo -u postgres ls -la ~/.ssh/
```

Verify that the public key appears in the `authorized_keys` file on the
backup server:

```bash
sudo -u backup-user cat ~/.ssh/authorized_keys
```

### Hostname Resolution Fails

**Symptom:** Nodes cannot reach each other by hostname.

**Solution:** Verify that `manage_host_file` is `true` so the collection
populates `/etc/hosts` on every node. If external DNS handles resolution,
confirm that each hostname resolves correctly:

```bash
nslookup node1.example.com
```

## Postgres

This section covers database initialization and startup issues.

### initdb Fails on RHEL

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

### Service Won't Start

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

### Extension Installation Fails

**Symptom:** The Spock or Snowflake extensions fail to install.

**Solution:** Verify that the pgEdge packages include the required extension
files:

```bash
ls -la /usr/pgsql-17/share/extension/spock*
ls -la /usr/pgsql-17/share/extension/snowflake*
```

Confirm that `shared_preload_libraries` lists the extensions and restart
Postgres after any configuration change.

## etcd

This section covers issues with the distributed coordination layer.

### Service Fails to Start

**Symptom:** The etcd service won't start after configuration.

**Solution:** Check the etcd logs:

```bash
sudo journalctl -u etcd -n 50 --no-pager
```

Check for port conflicts on etcd ports 2379 and 2380:

```bash
sudo netstat -tlnp | grep -E '2379|2380'
```

### Cluster Formation Fails

**Symptom:** etcd nodes cannot form a quorum.

**Solution:** Test network connectivity between nodes:

```bash
curl http://other-node:2379/health
```

Ensure the firewall allows etcd ports:

```bash
# RHEL
sudo firewall-cmd --add-port=2379/tcp --add-port=2380/tcp --permanent
sudo firewall-cmd --reload

# Debian
sudo ufw allow 2379/tcp && sudo ufw allow 2380/tcp
```

Verify that hostnames resolve correctly between all nodes.

### "cluster ID mismatch" Error

**Symptom:** etcd fails with a cluster ID mismatch.

**Solution:** Remove the existing data directory on the affected node and
restart the service:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

## Patroni

This section covers HA controller issues.

### Patroni Service Fails to Start

**Symptom:** The Patroni service won't start.

**Solution:** Check the Patroni logs:

```bash
sudo journalctl -u patroni -n 50 -f
```

Validate the configuration file:

```bash
sudo -u postgres patroni --validate-config /etc/patroni/patroni.yml
```

### etcd Connection Fails

**Symptom:** Patroni starts but cannot connect to etcd.

**Solution:** Verify that etcd is running and test connectivity using the
etcd TLS certificates:

```bash
sudo systemctl status etcd
sudo -u postgres /usr/local/etcd/etcdctl \
  --cacert=/etc/patroni/tls/ca.crt \
  --cert=/etc/patroni/tls/patroni.crt \
  --key=/etc/patroni/tls/patroni.key \
  endpoint health
```

Check that port 2379 is accessible from each Patroni node.

### Replication Not Working

**Symptom:** Replica nodes fail to stream changes from the primary.

**Solution:** Check the cluster status and replication user credentials:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yml list
```

Verify that `pg_hba.conf` allows replication connections from each replica
and that the `replication_user` password matches the Patroni configuration.

### Synchronous Replication Blocks Writes

**Symptom:** The cluster blocks all writes when a replica becomes
unavailable.

**Solution:** Review the `synchronous_mode_strict` setting. Disable strict
mode if availability is more important than zero-data-loss guarantees, then
check network connectivity to replica nodes.

## HAProxy

This section covers proxy routing issues.

### Service Fails to Start

**Symptom:** HAProxy won't start after configuration.

**Solution:** Validate the configuration syntax and check for port conflicts:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
sudo netstat -tlnp | grep -E '5432|5433|7000'
```

Review recent log entries for the cause:

```bash
sudo journalctl -u haproxy -n 50 --no-pager
```

### Health Checks Failing

**Symptom:** HAProxy marks all backends as DOWN.

**Solution:** Test the Patroni REST API on each backend node directly:

```bash
curl http://pg-node:8008/
curl http://pg-node:8008/replica
```

Ensure port 8008 is accessible from the HAProxy node.

### Connections Route to Wrong Node

**Symptom:** HAProxy sends write connections to a replica.

**Solution:** Check the current Patroni primary:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yml list
```

Verify that the HAProxy configuration uses the `/` (primary) health check
endpoint for write listeners and that the Patroni REST API responds
correctly on each node.

## Spock Replication

This section covers multi-zone replication issues.

### Subscription Creation Fails

**Symptom:** The Spock subscription creation command fails with a connection
or authentication error.

**Solution:** Test the connection from the local node to the remote node:

```bash
sudo -u postgres psql \
  "host=remote-node user=pgedge dbname=demo port=5432"
```

Verify that `pg_hba.conf` on the remote node allows connections from the
local node and that the `pgedge_user` credentials match.

### Subscriptions Not Syncing

**Symptom:** Subscriptions show as established but data does not replicate.

**Solution:** Query the subscription status:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.subscription;"
```

Check that the `status` column shows `replicating` for active subscriptions.
Review the Postgres logs for replication-related errors and check for table
constraint violations that may block replication.

### Replication Lag Increasing

**Symptom:** Replication lag between nodes grows continuously.

**Solution:** Check subscription status and exception history:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.sub_show_status();"
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.exception_status;"
```

Look for long-running transactions that block replication and verify that
sufficient bandwidth exists between zones.

### Subscription Shows Disabled State

**Symptom:** Spock marks a subscription as disabled and stops replicating.

**Solution:** Query the exception status to identify the root cause:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.exception_status;"
```

Resolve the underlying exception, then re-enable the subscription manually.
Adjust the `exception_behaviour` parameter if automatic handling is not
suitable.

## PgBackRest

This section covers backup and recovery issues.

### Initial Backup Fails

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

### SSH Backup Connection Fails

**Symptom:** PgBackRest cannot connect to the backup server over SSH.

**Solution:** Test SSH connectivity as the `postgres` user:

```bash
sudo -u postgres ssh backup-server
```

Verify that the public key in `~postgres/.ssh/id_rsa.pub` on the Postgres
node appears in the `authorized_keys` file on the backup server.

### S3 Connection Fails

**Symptom:** PgBackRest cannot connect to the S3 backup repository.

**Solution:** Verify the S3 credentials and bucket access:

```bash
aws s3 ls s3://bucket-name --region us-west-2
```

Confirm network connectivity to the S3 endpoint and that the IAM policy
grants the required permissions.

### Backup User Cannot Authenticate

**Symptom:** The backup user fails to authenticate to Postgres.

**Solution:** Confirm that the backup user exists and has the correct
privileges:

```bash
sudo -u postgres psql -c "\du backrest"
```

Verify that `pg_hba.conf` includes an entry for the backup user and that the
`backup_password` in the inventory matches the user's password.
