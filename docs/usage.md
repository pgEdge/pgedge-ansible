# Using the pgEdge Ansible Collection

This page provides usage examples for deploying and verifying pgEdge
clusters, including customization patterns and common operational workflows.

Complete the following steps before running any playbook:

1. Install the collection as described in the [Installation](installation.md)
   guide.
2. Review the [Architecture](architecture.md) page to choose a topology.
3. Prepare target hosts with SSH access and `sudo` privileges as described in
   the [Prerequisites](installation.md#prerequisites) section.
4. Create an [inventory file](simple_cluster.md#inventory) defining your
   cluster nodes and host groups.
5. Create a [playbook file](simple_cluster.md#playbook) that applies the
   required roles in order.

See the [Simple Cluster](simple_cluster.md) or [Ultra-HA Cluster](ultra_ha.md)
installation guides for example inventory and playbook files.

## Running a Playbook

After preparing your inventory and playbook files, run the deployment with the
`ansible-playbook` command:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

The playbook executes roles in sequence across all target hosts. Monitor the
output for task status and any warnings. When complete, verify the deployment
using the commands in the sections below.

## Verifying a Deployment

After deployment, verify each component using the commands in this section.

### Verifying Postgres

The following commands verify Postgres status and connectivity:

```bash
# Check service status on RHEL
systemctl status postgresql-17

# Check service status on Debian
systemctl status postgresql@17-main

# Connect to database
psql -U admin -d demo -c "SELECT version();"
```

### Verifying Spock Replication

The following commands verify Spock node and subscription status:

```bash
# Check node registration
sudo -u postgres psql -x -U admin -d demo \
  -c "SELECT * FROM spock.node;"

# Check subscription status
sudo -u postgres psql -x -U admin -d demo \
  -c "SELECT * FROM spock.subscription;"
```

### Verifying an HA Cluster

The following commands verify the Patroni and etcd cluster state:

```bash
# Check Patroni cluster status
sudo -u postgres patronictl \
  -c /etc/patroni/patroni.yml list

# Check etcd endpoint health
sudo -u postgres /usr/local/etcd/etcdctl \
  --cacert=/etc/patroni/tls/ca.crt \
  --cert=/etc/patroni/tls/patroni.crt \
  --key=/etc/patroni/tls/patroni.key \
  endpoint health

# Check HAProxy status
systemctl status haproxy
```

### Verifying Backups

The following commands verify the PgBackRest backup repository:

```bash
# Display backup repository info
pgbackrest --stanza=pgedge-demo-1 info

# Verify the latest backup
pgbackrest --stanza=pgedge-demo-1 check
```

## Common Workflows

This section provides details about recurring operational tasks.

### Testing HA Failover

The following command triggers a manual Patroni failover to verify that
HAProxy redirects connections to the new primary:

```bash
sudo -u postgres patronictl \
  -c /etc/patroni/patroni.yml failover demo
```

After the failover, connections through HAProxy continue automatically
without application changes.

### Adding a Node to a Simple Cluster

Add new nodes to a cluster only when database activity is at a minimum.
The collection does not currently use
[Zero-Downtime Add Node](https://docs.pgedge.com/spock-v5/development/modify/zodan/zodan_readme/)
functionality.

1. Add the new node to the inventory with a new zone number.
2. Run the playbook again to reconfigure the full cluster.
3. Verify Spock replication to the new node using the commands above.

### Disaster Recovery

When a node fails in a Spock cluster, restore it on a provisioned recovery
node that is separate from the existing cluster. The following commands
restore a Postgres instance from a PgBackRest backup:

```bash
# Stop Postgres
systemctl stop postgresql-17

# Clear the data directory
rm -rf /var/lib/pgsql/17/data/*

# Restore from backup
pgbackrest --stanza=pgedge-1 --delta restore

# Start Postgres
systemctl start postgresql-17
```

A recovered node cannot rejoin a Spock cluster by simple reconnection
because the cluster metadata will have diverged. Use
[pgEdge ACE](https://docs.pgedge.com/ace/) to reconcile data differences
and reintegrate the node safely.

