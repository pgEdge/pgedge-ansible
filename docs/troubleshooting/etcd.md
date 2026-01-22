# Solving etcd Issues

Etcd serves as the critical distributed coordination backend for pgEdge
clusters, managing cluster membership, configuration state, and leader
election. Configuration problems with etcd can render an entire cluster
unresponsive, making it impossible for nodes to discover each other or agree on
cluster state.

Troubleshooting etcd involves verifying downloads, validating checksums,
ensuring proper service initialization, and diagnosing network connectivity
between nodes. This section provides comprehensive guidance for resolving etcd
configuration issues, from initial installation problems to complex cluster
formation failures that prevent proper HA operation.

For problems not covered by this guide, please refer to the 
[etcd documenation](https://etcd.io/docs/).

## Download Fails from GitHub

**Symptom:** Failed to download etcd tarball from GitHub

**Solution:**

- Verify that the target host has internet connectivity and GitHub access.
- Check that the firewall allows HTTPS connections to github.com.

Test a manual download with the following command:

```bash
curl -LO https://github.com/etcd-io/etcd/releases/download/v3.6.5/etcd-v3.6.5-linux-amd64.tar.gz
```

You can also use an alternative mirror or local repository by setting the
`etcd_base_url` variable:

```yaml
etcd_base_url: "https://your-mirror.com/etcd/v{{ etcd_version }}"
```

## Checksum Verification Fails

**Symptom:** Download fails with checksum mismatch error

**Solution:**

- Verify that your inventory sets `etcd_version` correctly.
- Check for corrupted partial downloads in the temporary directory.

Clear temporary files and retry with the following command:

```bash
rm -rf ~/tmp/etcd-*
```

You can manually verify the checksum with the following commands:

```bash
wget https://github.com/etcd-io/etcd/releases/download/v3.6.5/SHA256SUMS
sha256sum ~/tmp/etcd-v3.6.5-linux-amd64.tar.gz
```

## Binary Not Executable

**Symptom:** The etcd binary exists but won't execute.

**Solution:**

Check the file permissions with the following command:

```bash
ls -la /usr/local/etcd/
```

Manually fix the permissions with the following commands:

```bash
sudo chmod 755 /usr/local/etcd/etcd
sudo chmod 755 /usr/local/etcd/etcdctl
sudo chmod 755 /usr/local/etcd/etcdutl
```

## User Creation Fails

**Symptom:** Ansible reports a failure to create the etcd system user.

**Solution:**

Check if the user already exists with the following command:

```bash
id etcd
```

- Verify that Ansible has sufficient permissions to create system users.
- Check for conflicts with existing users or groups on the system.

## Architecture Mismatch

**Symptom:** The binary fails to run with "cannot execute binary file" error

**Solution:**

Verify the system architecture with the following command:

```bash
uname -m
```

This role currently supports `x86_64` (amd64) only; for ARM systems, customize
the `etcd_package` variable:

```yaml
etcd_package: "etcd-v{{ etcd_version }}-linux-arm64"
```

## Service File Installation Fails

**Symptom:** The role failed to create the systemd service file.

**Solution:**

Verify that the system has systemd installed and running:

```bash
systemctl --version
```

Check the directory permissions with the following command:

```bash
ls -la /etc/systemd/system/
```

Manually reload systemd after applying fixes:

```bash
sudo systemctl daemon-reload
```

## etcd Service Fails to Start

**Symptom:** The etcd service won't start.

**Solution:**

Check the etcd logs for error messages:

```bash
sudo journalctl -u etcd -n 50 --no-pager
```

Check for port conflicts with the following command:

```bash
sudo netstat -tlnp | grep -E '2379|2380'
```

## Cluster Formation Fails

**Symptom:** Etcd nodes can't form a cluster.

**Solution:**

Check network connectivity between nodes with the following command:

```bash
curl http://other-node:2379/health
```

Ensure that the firewall allows etcd ports 2379 and 2380:

```bash
# RHEL
sudo firewall-cmd --add-port=2379/tcp --permanent
sudo firewall-cmd --add-port=2380/tcp --permanent
sudo firewall-cmd --reload

# Debian
sudo ufw allow 2379/tcp
sudo ufw allow 2380/tcp
```

Verify that hostnames resolve correctly:

```bash
ping hostname1
ping hostname2
```

## "cluster ID mismatch" Error

**Symptom:** Etcd fails with cluster ID mismatch error.

**Solution:**

This error occurs when data directories contain conflicting cluster state.
Remove the existing data and reconfigure the cluster:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

Ensure that all nodes start fresh or that all nodes share a consistent state.

## "member already exists" Error

**Symptom:** Node fails to join with "member already exists".

**Solution:**

Check the existing cluster members with the following command:

```bash
/usr/local/etcd/etcdctl member list
```

Remove the old member with the following command:

```bash
/usr/local/etcd/etcdctl member remove <member-id>
```

Clear the data directory and restart the service:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

## Slow Performance or Timeouts

**Symptom:** Etcd operations are slow or timing out.

**Solution:**

- Check the network latency between etcd nodes; latency should stay below 10ms.
- Ensure that etcd nodes have sufficient I/O performance for cluster operations.
- Review the etcd logs for slow disk warnings.
- Consider using dedicated SSDs for the etcd data directory.
