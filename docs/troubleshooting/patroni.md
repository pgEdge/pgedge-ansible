# Patroni

This page covers HA controller issues.

## Patroni Service Fails to Start

**Symptom:** The Patroni service won't start.

**Solution:** Check the Patroni logs:

```bash
sudo journalctl -u patroni -n 50 -f
```

Validate the configuration file:

```bash
sudo -u postgres patroni --validate-config /etc/patroni/patroni.yml
```

## etcd Connection Fails

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

## Replication Not Working

**Symptom:** Replica nodes fail to stream changes from the primary.

**Solution:** Check the cluster status and replication user credentials:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yml list
```

Verify that `pg_hba.conf` allows replication connections from each replica
and that the `replication_user` password matches the Patroni configuration.

## Synchronous Replication Blocks Writes

**Symptom:** The cluster blocks all writes when a replica becomes unavailable.

**Solution:** Review the `synchronous_mode_strict` setting. Disable strict
mode if availability is more important than zero-data-loss guarantees, then
check network connectivity to replica nodes.
