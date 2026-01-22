# Solving Patroni Issues

Patroni serves as the intelligent controller that manages Postgres high
availability by orchestrating failover, leader election, and replica promotion
through etcd. Problems with Patroni installation often stem from Python
environment issues, missing development dependencies, or permission
restrictions that prevent proper package installation and binary placement.

Configuration errors can leave Postgres instances unable to communicate with
etcd or other cluster members, resulting in failed cluster formation. This
section covers the entire spectrum of Patroni troubleshooting, from
installation failures to cluster connectivity issues and replication problems
that prevent proper HA operation.

For problems not covered by this guide, please refer to the 
[Patroni documenation](https://patroni.readthedocs.io/en/latest/README.html).

## pipx Installation Fails

**Symptom:** Ansible fails to install pipx on RHEL systems.

**Solution:**

Verify that Python 3 and pip are installed:

```bash
python3 --version
pip3 --version
```

Manually install pipx as the `postgres` user:

```bash
sudo -u postgres python3 -m pip install --user pipx
sudo -u postgres python3 -m pipx ensurepath
```

Verify that the PATH includes pipx:

```bash
pipx --version
```

## Patroni Installation Fails

**Symptom:** Pipx fails to install patroni.

**Solution:**

Check the `postgres` user's environment:

```bash
sudo -u postgres pipx list
```

Verify that pipx has initialized the environment:

```bash
sudo -u postgres pipx ensurepath
```

Check for compilation errors caused by missing development packages and install
the necessary dependencies:

```bash
# Debian/Ubuntu
sudo apt install python3-dev libpq-dev

# RHEL/Rocky
sudo dnf install python3-devel postgresql-devel
```

## Binary Not Found After Installation

**Symptom:** The shell cannot find the `patroni` command.

**Solution:**

Verify the installation location with the following command:

```bash
sudo -i -u postgres ls -la .local/bin/
```

Check that the PATH includes the `patroni_bin_dir` directory:

```bash
sudo -i -u postgres printenv | grep PATH
```

Manually add the path to the `.profile`, `.bash_profile`, or `.bashrc` files:

```bash
export PATH="$PATH:/var/lib/pgsql/.local/bin"
```

## Permission Denied on Config Directory

**Symptom:** Ansible cannot write to the `/etc/patroni` directory.

**Solution:**

Verify the directory ownership with the following command:

```bash
sudo ls -la /etc/patroni
```

Fix the permissions with the following commands:

```bash
sudo chown postgres:postgres /etc/patroni
sudo chmod 700 /etc/patroni
```

## Patroni Service Fails to Start

**Symptom:** The Patroni service won't start.

**Solution:**

Check the Patroni logs for error messages:

```bash
sudo journalctl -u patroni -n 50 -f
```

Verify the configuration syntax with the following command:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patroni --validate-config /etc/patroni/patroni.yaml
```

Check the etcd connectivity with the following command:

```bash
curl http://localhost:2379/health
```

## etcd Connection Fails

**Symptom:** Patroni can't connect to etcd.

**Solution:**

Verify that etcd is running:

```bash
sudo systemctl status etcd
```

Test the etcd connectivity with the following command:

```bash
curl http://localhost:2379/v3/cluster/member/list
```

- Check that the firewall allows traffic on port 2379.
- Verify that the etcd hostname resolves correctly on all nodes.

## Cluster Formation Fails

**Symptom:** Patroni starts but can't form a cluster with other nodes.

**Solution:**

Check the etcd keys for the cluster:

```bash
/usr/local/etcd/etcdctl get --prefix /db/pgedge/
```

- Verify that all nodes can see each other in etcd.
- Check for split-brain scenarios in the cluster.
- Review the Patroni logs on all nodes for error messages.
- Ensure that the primary node started first in the cluster.

## "Pending Restart" Status Persists

**Symptom:** Patroni displays "Pending restart" after configuration changes.

**Solution:**

Restart a specific node using `patronictl`:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge <hostname>
```

Alternatively, restart all nodes in the cluster:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge
```

## Replication Not Working

**Symptom:** Replicas fail to stream from the primary node.

**Solution:**

Check the Patroni cluster status:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml list
```

- Verify that the replication user credentials match the configuration.
- Check that the `pg_hba.conf` file allows replication connections.
- Verify the network connectivity between nodes.
- Check the Postgres logs for replication errors.

## Synchronous Replication Blocks Writes

**Symptom:** The cluster blocks writes when synchronous replicas become
unavailable.

**Solution:**

- Review the `synchronous_mode_strict` setting in the Patroni configuration.
- Disable strict mode temporarily if the situation requires immediate writes.
- Ensure that sufficient healthy replicas are available for synchronous mode.
- Check the network connectivity to replica nodes.
