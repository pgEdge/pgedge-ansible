# Troubleshooting

This guide provides solutions to common issues encountered when deploying and managing pgEdge clusters with the Ansible Collection.

## Installation Issues

### Collection Not Found

If Ansible cannot find the collection after installation:

1. Check the installation path with the following command:

   ```bash
   ansible-galaxy collection list
   ```

2. Verify the collections path in your `ansible.cfg`:

   ```ini
   [defaults]
   collections_paths = ~/.ansible/collections:/usr/share/ansible/collections
   ```

### Build Failures

If `make install` fails:

- Ensure you have the `ansible-galaxy` command available.
- Check that you have write permissions to the collections directory.
- Verify the `VERSION` file exists in the repository root.

### SSH Connection Issues

If Ansible cannot connect to hosts:

- Verify SSH access manually with the following command: `ssh user@host`.
- Check SSH key permissions with the following command: `chmod 600 ~/.ssh/id_rsa`.
- Ensure the remote user has appropriate sudo privileges.
- Review your inventory file for correct hostnames and connection parameters.

## Repository Configuration

### Repository Package Download Fails

**Symptom:** Failed to download repository package from pgEdge URLs

**Solution:**

- Verify internet connectivity from target hosts.
- Check firewall rules allow HTTPS (443) outbound.
- Verify DNS resolution for `apt.pgedge.com` or `dnf.pgedge.com`.
- Check proxy settings if using HTTP proxy.

Test connectivity with the following commands:

```bash
curl -I https://apt.pgedge.com/repodeb/pgedge-release_latest_all.deb
curl -I https://dnf.pgedge.com/reporpm/pgedge-release-latest.noarch.rpm
```

### GPG Key Import Fails

**Symptom:** GPG key verification errors during repository installation

**Solution:**

- Verify the GPG key URL is accessible.
- Check system time is correct (affects key validity).
- Manually import the key with the following commands:

```bash
# Debian/Ubuntu
curl https://apt.pgedge.com/keys/pgedge.pub | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/pgedge.gpg

# RHEL/Rocky
sudo rpm --import https://dnf.pgedge.com/keys/pgedge.pub
```

### Package Cache Not Updated

**Symptom:** pgEdge packages not found after repository installation

**Solution:**

Manually update the package cache with the following commands:

```bash
# Debian/Ubuntu
sudo apt update

# RHEL/Rocky
sudo dnf makecache
```

Verify the repository is enabled:

```bash
# Debian/Ubuntu
apt-cache policy | grep pgedge

# RHEL/Rocky
dnf repolist | grep pgedge
```

## Package Installation

### Package Not Found

**Symptom:** Package installation fails with "package not found" error

**Solution:**

- Verify the `install_repos` role completed successfully.
- Check the package cache is updated with the following commands:

```bash
# Debian/Ubuntu
sudo apt update
apt-cache search pgedge-enterprise

# RHEL/Rocky
sudo dnf makecache
dnf search pgedge-enterprise
```

- Verify the correct repository is configured with the following commands:

```bash
# Debian/Ubuntu
cat /etc/apt/sources.list.d/pgedge.sources

# RHEL/Rocky
cat /etc/yum.repos.d/pgedge.repo
```

### Version Mismatch

**Symptom:** Wrong Postgres version installed

**Solution:**

- Verify the `pg_version` variable is set correctly.
- Check available package versions with the following commands:

```bash
# Debian/Ubuntu
apt-cache policy pgedge-enterprise-all-17

# RHEL/Rocky
dnf list pgedge-enterprise-all_17
```

- Ensure the version-specific package exists in the repository.

### Dependency Conflicts

**Symptom:** Package installation fails due to dependency conflicts

**Solution:**

Check for conflicting Postgres installations:

```bash
# List installed Postgres packages
dpkg -l | grep postgres  # Debian/Ubuntu
rpm -qa | grep postgres  # RHEL/Rocky
```

Remove conflicting packages if safe:

```bash
# Debian/Ubuntu
sudo apt remove [conflicting packages]

# RHEL/Rocky
sudo dnf remove [conflicting packages]
```

### Network Timeouts

**Symptom:** Package downloads timeout or fail intermittently

**Solution:**

- The roles include 5 retries with 20-second delays.
- For persistent issues, check network connectivity.
- Verify repository servers are accessible.
- Consider using a local package mirror.

### Lock Timeout on Debian

**Symptom:** "Could not get lock" error on Debian/Ubuntu

**Solution:**

Check for hung apt processes:

```bash
ps aux | grep apt
```

Wait for other package operations to complete. The role uses a 300-second timeout.

### Cron Package Conflicts

**Symptom:** Cron installation fails due to conflicts

**Solution:**

Check for existing cron installations:

```bash
# Debian/Ubuntu
dpkg -l '*cron*'

# RHEL/Rocky
rpm -qa | grep cron
```

Remove conflicting packages if safe:

```bash
# RHEL only (if anacron conflicts)
sudo dnf remove cronie-anacron
sudo dnf install cronie
```

## System Configuration

### Package Installation Failures

**Symptom:** Package installation fails with repository errors

**Solution:**

- Verify internet connectivity.
- Check repository configuration.
- Update the package cache manually with the following commands:
    - Debian: `apt update`
    - RHEL: `dnf makecache`

### SELinux Reboot Issues

**Symptom:** System doesn't come back online after SELinux configuration

**Solution:**

- Verify SSH connectivity is maintained through reboots.
- Check firewall rules allow SSH.
- Increase wait timeout in Ansible configuration.
- Manually check system status after reboot.

### SSH Key Problems

**Symptom:** SSH keys not properly generated or distributed

**Solution:**

- Verify the `postgres` user exists.
- Check permissions on the `.ssh` directory (700).
- Check permissions on SSH keys (600 for private, 644 for public).
- Ensure Ansible has write access to the `host-keys` directory.

### Host File Issues

**Symptom:** Nodes cannot resolve each other's hostnames

**Solution:**

- Verify `/etc/hosts` contains all cluster nodes.
- Check that `manage_host_file: true`.
- Ensure the inventory contains correct hostnames/IPs.
- Test resolution with the following command: `ping hostname`.

## etcd Configuration

### Download Fails from GitHub

**Symptom:** Failed to download etcd tarball from GitHub

**Solution:**

- Verify internet connectivity and GitHub access.
- Check firewall allows HTTPS to github.com.
- Test manual download with the following command:

```bash
curl -LO https://github.com/etcd-io/etcd/releases/download/v3.6.5/etcd-v3.6.5-linux-amd64.tar.gz
```

Use an alternative mirror or local repository:

```yaml
etcd_base_url: "https://your-mirror.com/etcd/v{{ etcd_version }}"
```

### Checksum Verification Fails

**Symptom:** Download fails with checksum mismatch error

**Solution:**

- Verify the `etcd_version` is correct.
- Check for corrupted partial downloads.
- Clear temporary files and retry with the following commands:

```bash
rm -rf ~/tmp/etcd-*
```

Manually verify the checksum:

```bash
wget https://github.com/etcd-io/etcd/releases/download/v3.6.5/SHA256SUMS
sha256sum ~/tmp/etcd-v3.6.5-linux-amd64.tar.gz
```

### Binary Not Executable

**Symptom:** etcd binary exists but won't execute

**Solution:**

Check file permissions:

```bash
ls -la /usr/local/etcd/
```

Manually fix permissions:

```bash
sudo chmod 755 /usr/local/etcd/etcd
sudo chmod 755 /usr/local/etcd/etcdctl
sudo chmod 755 /usr/local/etcd/etcdutl
```

### User Creation Fails

**Symptom:** Failed to create etcd system user

**Solution:**

Check if the user already exists:

```bash
id etcd
```

- Verify sufficient permissions to create users.
- Check for conflicts with existing users/groups.

### Architecture Mismatch

**Symptom:** Binary won't run, "cannot execute binary file" error

**Solution:**

Verify the system architecture:

```bash
uname -m
```

This role currently supports `x86_64` (amd64) only. For ARM systems, customize the `etcd_package` variable:

```yaml
etcd_package: "etcd-v{{ etcd_version }}-linux-arm64"
```

### Service File Installation Fails

**Symptom:** systemd service file not created

**Solution:**

Verify systemd is installed and running:

```bash
systemctl --version
```

Check directory permissions:

```bash
ls -la /etc/systemd/system/
```

Manually reload systemd after fixes:

```bash
sudo systemctl daemon-reload
```

### etcd Service Fails to Start

**Symptom:** etcd service won't start

**Solution:**

Check etcd logs:

```bash
sudo journalctl -u etcd -n 50 --no-pager
```

Check for port conflicts:

```bash
sudo netstat -tlnp | grep -E '2379|2380'
```

### Cluster Formation Fails

**Symptom:** etcd nodes can't form cluster

**Solution:**

- Verify all nodes are listed in initial-cluster.
- Check network connectivity between nodes with the following command:

```bash
curl http://other-node:2379/health
```

Ensure firewall allows etcd ports (2379, 2380):

```bash
# RHEL
sudo firewall-cmd --add-port=2379/tcp --permanent
sudo firewall-cmd --add-port=2380/tcp --permanent
sudo firewall-cmd --reload

# Debian
sudo ufw allow 2379/tcp
sudo ufw allow 2380/tcp
```

Verify hostnames resolve correctly:

```bash
ping hostname1
ping hostname2
```

### "cluster ID mismatch" Error

**Symptom:** etcd fails with cluster ID mismatch

**Solution:**

This occurs when data directories have conflicting cluster state. Remove existing data and reconfigure:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

Ensure all nodes start fresh or all have consistent state.

### "member already exists" Error

**Symptom:** Node fails to join with "member already exists"

**Solution:**

Check existing cluster members:

```bash
/usr/local/etcd/etcdctl member list
```

Remove the old member:

```bash
/usr/local/etcd/etcdctl member remove <member-id>
```

Clear the data directory and restart:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

### Slow Performance or Timeouts

**Symptom:** etcd operations are slow or timing out

**Solution:**

- Check network latency between etcd nodes (should be <10ms for optimal performance).
- Ensure etcd nodes have sufficient I/O performance.
- Review etcd logs for slow disk warnings.
- Consider using dedicated SSDs for etcd data.

## Patroni Installation and Configuration

### pipx Installation Fails

**Symptom:** Failed to install pipx on RHEL systems

**Solution:**

Verify Python 3 and pip are installed:

```bash
python3 --version
pip3 --version
```

Manually install pipx as the postgres user:

```bash
sudo -u postgres python3 -m pip install --user pipx
sudo -u postgres python3 -m pipx ensurepath
```

Verify pipx is in PATH:

```bash
pipx --version
```

### Patroni Installation Fails

**Symptom:** pipx install patroni command fails

**Solution:**

Check the postgres user's environment:

```bash
sudo -u postgres pipx list
```

Verify the pipx environment is initialized:

```bash
sudo -u postgres pipx ensurepath
```

Check for compilation errors (missing development packages):

```bash
# Debian/Ubuntu
sudo apt install python3-dev libpq-dev

# RHEL/Rocky
sudo dnf install python3-devel postgresql-devel
```

### Binary Not Found After Installation

**Symptom:** patroni command not found

**Solution:**

Verify the installation location:

```bash
sudo -i -u postgres ls -la .local/bin/
```

Check PATH includes `patroni_bin_dir`:

```bash
sudo -i -u postgres printenv | grep PATH
```

Manually add to PATH in `.profile`, `.bash_profile`, or `.bashrc` files:

```bash
export PATH="$PATH:/var/lib/pgsql/.local/bin"
```

### Permission Denied on Config Directory

**Symptom:** Cannot write to `/etc/patroni`

**Solution:**

Verify directory ownership:

```bash
sudo ls -la /etc/patroni
```

Fix permissions:

```bash
sudo chown postgres:postgres /etc/patroni
sudo chmod 700 /etc/patroni
```

### Patroni Service Fails to Start

**Symptom:** Patroni service won't start

**Solution:**

Check Patroni logs:

```bash
sudo journalctl -u patroni -n 50 -f
```

Verify configuration syntax:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patroni --validate-config /etc/patroni/patroni.yaml
```

Check etcd connectivity:

```bash
curl http://localhost:2379/health
```

### etcd Connection Fails

**Symptom:** Patroni can't connect to etcd

**Solution:**

Verify etcd is running:

```bash
sudo systemctl status etcd
```

Test etcd connectivity:

```bash
curl http://localhost:2379/v3/cluster/member/list
```

- Check firewall allows port 2379.
- Verify etcd hostname resolution.

### Cluster Formation Fails

**Symptom:** Patroni starts but cluster doesn't form

**Solution:**

Check etcd keys:

```bash
/usr/local/etcd/etcdctl get --prefix /db/pgedge/
```

- Verify all nodes see each other in etcd.
- Check for split-brain scenarios.
- Review Patroni logs on all nodes.
- Ensure the primary started first.

### "Pending Restart" Status Persists

**Symptom:** Patroni shows "Pending restart" after configuration changes

**Solution:**

Restart using patronictl:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge <hostname>
```

Or restart all nodes:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge
```

### Replication Not Working

**Symptom:** Replicas not streaming from primary

**Solution:**

Check Patroni cluster status:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml list
```

- Verify replication user credentials.
- Check pg_hba.conf allows replication connections.
- Verify network connectivity between nodes.
- Check PostgreSQL logs for replication errors.

### Synchronous Replication Blocks Writes

**Symptom:** Writes are blocked when synchronous replicas are unavailable

**Solution:**

- Review the `synchronous_mode_strict` setting.
- Disable strict mode temporarily if needed.
- Ensure sufficient healthy replicas are available.
- Check network connectivity to replica nodes.

## PostgreSQL Configuration

### initdb Fails on RHEL

**Symptom:** `postgresql-{{ pg_version }}-setup initdb` command fails

**Solution:**

- Verify Postgres packages are installed.
- Check data directory permissions:

```bash
ls -la /var/lib/pgsql/17
```

Manually initialize:

```bash
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
```

### SSL Certificate Generation Fails

**Symptom:** Cannot create SSL certificates

**Solution:**

Verify OpenSSL is installed:

```bash
openssl version
```

- Check data directory permissions.
- Manually generate certificates:

```bash
sudo -u postgres openssl req -new -x509 -days 365 -nodes \
  -text -out /var/lib/pgsql/17/data/server.crt \
  -keyout /var/lib/pgsql/17/data/server.key \
  -subj "/CN=$(hostname)"
```

### Service Won't Start

**Symptom:** Postgres service fails to start

**Solution:**

Check Postgres logs:

```bash
# Systemd
sudo journalctl -u postgresql-17 -f --no-pager

# Debian
sudo tail -f /var/log/postgresql/postgresql-17-main.log

# RHEL
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

Verify configuration syntax:

```bash
sudo -u postgres /usr/pgsql-17/bin/postgres -D /var/lib/pgsql/17/data -C config_file
```

Check for port conflicts:

```bash
netstat -tnlp | grep 5432
```

### Extension Installation Fails

**Symptom:** Spock or Snowflake extension fails to install

**Solution:**

Verify extensions are included in pgEdge packages:

```bash
# Check for extension files
ls -la /usr/pgsql-17/share/extension/spock*
ls -la /usr/pgsql-17/share/extension/snowflake*
```

- Check `shared_preload_libraries` is set correctly.
- Restart Postgres after configuration changes.
- Manually test extension creation:

```bash
sudo -u postgres psql -c "CREATE EXTENSION spock CASCADE;"
```

### Connection Refused

**Symptom:** Cannot connect to Postgres after setup

**Solution:**

- Verify Postgres is running: `sudo systemctl status postgresql-17`.
- Check Postgres is listening on the correct port: `netstat -tnlp | grep 5432`.
- Verify firewall rules allow PostgreSQL port.
- Check pg_hba.conf includes your connection source.
- Test local connection: `sudo -u postgres psql`.

## HAProxy Configuration

### HAProxy Service Fails to Start

**Symptom:** HAProxy service won't start

**Solution:**

Check HAProxy logs:

```bash
# View logs
sudo journalctl -u haproxy -n 50 --no-pager

# Or on Debian
sudo tail -f /var/log/haproxy.log
```

Validate configuration:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

Check for port conflicts:

```bash
sudo netstat -tlnp | grep -E '5432|5433|7000'
```

### Health Checks Failing

**Symptom:** All backends marked as DOWN

**Solution:**

Verify Patroni is running on PostgreSQL nodes:

```bash
sudo systemctl status patroni
```

Test Patroni REST API manually:

```bash
curl http://pg-node:8008/
curl http://pg-node:8008/replica
```

Check network connectivity:

```bash
telnet pg-node 8008
```

Verify firewall allows port 8008:

```bash
# RHEL
sudo firewall-cmd --list-all

# Debian
sudo ufw status
```

### Cannot Connect Through HAProxy

**Symptom:** Database connections to HAProxy fail

**Solution:**

Check HAProxy statistics:

```bash
curl http://haproxy-host:7000/
```

- Verify at least one backend is UP.
- Test direct connection to backend: `psql -h pg-node -p 5432 -U admin`.
- Check HAProxy is listening: `sudo netstat -tlnp | grep haproxy`.

### Connections Route to Wrong Node

**Symptom:** HAProxy routes to replica instead of primary

**Solution:**

Check Patroni cluster status:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yaml list
```

- Verify health check endpoints are configured correctly.
- Check Patroni REST API responds correctly.
- Review HAProxy configuration for correct health check paths.

## Spock Replication

### Spock Node Creation Fails

**Symptom:** Failed to create Spock node

**Solution:**

Verify Spock extension is installed:

```bash
sudo -u postgres psql -d dbname -c "\dx spock"
```

- Check PostgreSQL is running and accessible.
- Verify `pgedge_user` exists and has permissions.
- Review PostgreSQL logs for errors.

### Subscription Creation Fails

**Symptom:** Failed to create Spock subscription

**Solution:**

Verify the remote node is accessible:

```bash
sudo -u postgres psql "host=remote-node user=pgedge dbname=demo port=5432"
```

- Ensure `pg_hba.conf` allows connections from the current node.
- Verify `pgedge_user` credentials are correct.
- Check network connectivity and firewall rules.
- Review the `.pgpass` file has the correct password.

### Proxy Connectivity Fails

**Symptom:** Cannot connect through HAProxy

**Solution:**

Verify HAProxy is running:

```bash
sudo systemctl status haproxy
```

Test HAProxy connectivity:

```bash
psql "host=haproxy-host port=5432 user=pgedge dbname=postgres"
```

- Check HAProxy configuration and health checks.
- Verify Patroni is running on backend nodes.
- Review HAProxy logs for errors.

### Subscriptions Not Syncing

**Symptom:** `sub_wait_for_sync()` times out or hangs

**Solution:**

Check subscription status:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.subscription;"
```

- Ensure the `status` column shows `replicating`.
- Review PostgreSQL logs for replication errors.
- Verify network stability between nodes.
- Check for table conflicts or constraint violations.

### Replication Lag Increasing

**Symptom:** Growing lag between nodes

**Solution:**

Check replication status:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.sub_show_status();"
```

Look for Spock worker exceptions:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.exception_status;"
```

- Verify network bandwidth between nodes.
- Check for long-running transactions.
- Review conflict resolution settings.
- Consider optimizing table designs or indexes.

### Subscription Shows "Disabled" State

**Symptom:** Subscription marked as disabled

**Solution:**

Look for Spock worker exceptions:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.exception_status;"
```

- Resolve the underlying exception.
- Re-enable the subscription manually if needed.
- Review exception_behaviour configuration.

## Backup and Recovery

### Initial Backup Fails

**Symptom:** stanza-create or initial backup fails

**Solution:**

- Verify PostgreSQL is running.
- Check pgBackRest configuration:

```bash
sudo -u postgres pgbackrest info
```

Test the backup command manually:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 check
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 backup --type=full
```

Check logs:

```bash
sudo tail -f /var/log/pgbackrest/*
```

### SSH Connection Fails

**Symptom:** Cannot connect to backup server via SSH

**Solution:**

Test SSH connectivity:

```bash
sudo -u postgres ssh backup-server
```

Verify SSH keys:

```bash
sudo -u postgres ls -la ~/.ssh/
```

- Check authorized_keys on the backup server.
- Verify firewall allows SSH (port 22).

### S3 Connection Fails

**Symptom:** Cannot connect to S3 repository

**Solution:**

- Verify S3 credentials are correct.
- Test S3 access:

```bash
aws s3 ls s3://bucket-name --region us-west-2
```

- Check network connectivity to S3 endpoint.
- Verify the bucket exists and is accessible.
- Check IAM permissions for backup operations.

### Archive Command Fails

**Symptom:** WAL archiving errors in PostgreSQL logs

**Solution:**

Check PostgreSQL logs:

```bash
sudo tail -f /var/lib/pgsql/17/data/log/postgresql-*.log
```

Test the archive command manually:

```bash
sudo -u postgres pgbackrest --stanza=pgedge-demo-1 archive-push /path/to/wal/file
```

- Verify the backup repository is accessible.
- Check pgBackRest configuration.
- Ensure the initial backup completed successfully.

### Backup User Cannot Connect

**Symptom:** Backup user authentication fails

**Solution:**

Verify the backup user exists:

```bash
sudo -u postgres psql -c "\du backrest"
```

- Check pg_hba.conf includes the backup user.
- Verify the backup user password is correct.
- Test connection manually from backup server.

## Ansible Execution

### Playbook Failures

Run with increased verbosity:

```bash
ansible-playbook playbook.yaml -vvv
```

Check mode (dry run):

```bash
ansible-playbook playbook.yaml --check
```

### Connection Issues

Test connectivity:

```bash
ansible all -i inventory.yaml -m ping
```

Check SSH access:

```bash
ansible all -i inventory.yaml -m shell -a "hostname"
```

### Check Mode Limitations

**Symptom:** Tasks fail in check mode

**Solution:**

Some tasks may fail in check mode if they depend on changes from previous tasks. This is expected behavior.

### Debugging Individual Roles

Run a specific role in isolation:

```bash
ansible-playbook playbook.yml --tags role_name
```

### Role Dependencies Not Met

**Symptom:** Role fails due to missing prerequisites

**Solution:**

- Ensure roles execute in the proper order.
- Verify prerequisite roles completed successfully.
- Check that all required variables are defined.

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [GitHub repository](https://github.com/pgEdge/pgedge-ansible) for known issues.
2. Review role-specific documentation in the [roles section](roles/index.md).
3. Examine system logs for detailed error messages.
4. Open an issue on GitHub with detailed information about your environment and the problem.
