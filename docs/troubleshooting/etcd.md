# etcd

This page covers issues with the distributed coordination layer.

## Service Fails to Start

**Symptom:** The etcd service won't start after configuration.

**Solution:** Check the etcd logs:

```bash
sudo journalctl -u etcd -n 50 --no-pager
```

Check for port conflicts on etcd ports 2379 and 2380:

```bash
sudo netstat -tlnp | grep -E '2379|2380'
```

## Cluster Formation Fails

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

## "cluster ID mismatch" Error

**Symptom:** etcd fails with a cluster ID mismatch.

**Solution:** Remove the existing data directory on the affected node and
restart the service:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```
