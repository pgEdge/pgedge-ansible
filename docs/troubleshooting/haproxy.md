# HAProxy

This page covers proxy routing issues.

## Service Fails to Start

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

## Health Checks Failing

**Symptom:** HAProxy marks all backends as DOWN.

**Solution:** Test the Patroni REST API on each backend node directly:

```bash
curl http://pg-node:8008/
curl http://pg-node:8008/replica
```

Ensure port 8008 is accessible from the HAProxy node.

## Connections Route to Wrong Node

**Symptom:** HAProxy sends write connections to a replica.

**Solution:** Check the current Patroni primary:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yml list
```

Verify that the HAProxy configuration uses the `/` (primary) health check
endpoint for write listeners and that the Patroni REST API responds
correctly on each node.
