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

## Patroni Service Fails to Start

**Symptom:** The Patroni service won't start.

**Solution:**

Check the Patroni logs for error messages:

```bash
sudo journalctl -u patroni -n 50 -f
```

Verify the configuration syntax with the following command:

```bash
sudo -u postgres patroni --validate-config /etc/patroni/17-demo.yml
```

Check the etcd connectivity with the following command:

```bash
sudo -u postgres /usr/local/etcd/etcdctl \
     --cacert=/etc/patroni/tls/ca.crt \
     --cert=/etc/patroni/tls/patroni.crt \
     --key=/etc/patroni/tls/patroni.key \
     endpoint health
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
sudo -u postgres /usr/local/etcd/etcdctl \
     --cacert=/etc/patroni/tls/ca.crt \
     --cert=/etc/patroni/tls/patroni.crt \
     --key=/etc/patroni/tls/patroni.key \
     member list
```

- Check that any firewalls allow traffic on port 2379.
- Verify that the etcd hostname resolves correctly on all nodes.

## Cluster Formation Fails

**Symptom:** Patroni starts but can't form a cluster with other nodes.

**Solution:**

Check the etcd keys for the cluster:

```bash
sudo -u postgres /usr/local/etcd/etcdctl \
     --cacert=/etc/patroni/tls/ca.crt \
     --cert=/etc/patroni/tls/patroni.crt \
     --key=/etc/patroni/tls/patroni.key \
     get --prefix /db
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
sudo -u postgres patronictl -c /etc/patroni/patroni.yml restart 17-demo <hostname>
```

Alternatively, restart all nodes in the cluster:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yml restart 17-demo
```

## Replication Not Working

**Symptom:** Replicas fail to stream from the primary node.

**Solution:**

Check the Patroni cluster status:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yml list
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
