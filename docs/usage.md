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

The following commands verify the Postgres server's status and availability:

```bash
# Check service status on RHEL
systemctl status postgresql-17

# Check service status on Debian
systemctl status postgresql@17-main

# Connect to database
psql -U admin -d demo -c "SELECT version();"
```

### Verifying Spock Replication

The following commands verify the Spock nodes and subscription status:

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
  -c /etc/patroni/patroni.yml failover 17-demo
```

The final argument is the Patroni scope, which `patroni_scope` sets and which
defaults to the Postgres version and the cluster name joined by a hyphen. Run
`patronictl list` first when the deployment overrides `patroni_scope`, because
that command reports the name to pass here.

After the failover, connections through HAProxy continue automatically
without application changes.

### Adding a Zone to a Running Cluster

A cluster that already holds data can grow by a zone while it keeps taking
writes, on a simple cluster or an Ultra-HA one. The existing zones may be
restarted one node at a time before the copy, to enlarge their worker and
replication pools. The new zone copies every
database in `db_names` from an existing zone and receives every write made
during the copy, with nothing lost or applied twice.

1. Add the new zone's hosts to the inventory with a new zone number.
2. Run the deployment playbook again against the whole inventory, naming the
   zone:

    ```bash
    ansible-playbook -i inventory.yaml playbook.yaml -e pgedge_join_zones=4
    ```

3. Wait for the run to finish before sending applications to the new zone.

A join that stops partway resumes when you run the same command again. Without
`pgedge_join_zones`, the run refuses a zone that isn't yet part of a cluster
that holds data. See
[Adding a Zone to a Running Cluster](add_zone.md) for what the join does, how
long it takes, its effect on the existing zones, and what to do when it
fails.

!!! warning "One Major Change per Run"

    Only modify one major aspect of the cluster at a time. New replicas, new
    databases, new zones, and similar changes should not be mixed in a single
    run.

To take a zone back out of the cluster, use
[`remove_zone`](roles/remove_zone.md).

### Adding a Node to an Ultra-HA Zone

A zone in an Ultra-HA cluster can grow while it runs. The new node joins the
zone as another Patroni replica, without moving the zone's leader.

1. Add the new node to the inventory with the zone number of the zone it
   joins.
2. Run the deployment playbook again against the whole inventory.

Where the collection runs etcd, `setup_etcd` adds the new node to its zone's
etcd cluster before starting it, first as a learner that does not count toward
the zone's quorum, and then promotes it to a voting member once it has caught
up. The zone's other members are then restarted one at a time, so their
configuration lists the new node too. See
[setup_etcd](roles/setup_etcd.md#joining-a-running-zone).

Prefer an odd number of nodes in each zone. etcd needs a majority of a zone's
members to keep running, so a zone of four survives the loss of one member, no
more than a zone of three does, and a zone of two survives the loss of none.

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

