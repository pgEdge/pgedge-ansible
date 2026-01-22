# Solving HAProxy Issues

HAProxy provides the critical connection routing layer that ensures connections
reach the primary Postgres node while maintaining high availability through
intelligent health checks. Problems with HAProxy configuration can result in
failed connections, incorrect node routing, or complete service unavailability.

Troubleshooting HAProxy involves verifying service startup, validating
configuration syntax, ensuring proper health check endpoints, and debugging
connection routing logic. This section offers targeted solutions for
HAProxy-specific issues that impact client connectivity and load distribution
across your pgEdge cluster.

For problems not covered by this guide, please refer to the 
[HAProxy managemetn guide](https://docs.haproxy.org/3.3/management.html).

## HAProxy Service Fails to Start

This issue occurs when HAProxy cannot initialize due to configuration errors,
port conflicts, or missing dependencies.

**Symptom:** The HAProxy service will not start or exits immediately after 
starting.

**Solution:**

In the following example, the `journalctl` command displays recent HAProxy log
entries:

```bash
sudo journalctl -u haproxy -n 50 --no-pager
```

On Debian systems, HAProxy may log to a dedicated file:

```bash
sudo tail -f /var/log/haproxy.log
```

Validate the configuration syntax before starting the service:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

Check for port conflicts that may prevent HAProxy from binding:

```bash
sudo netstat -tlnp | grep -E '5432|5433|7000'
```

## Health Checks Failing

HAProxy uses health checks to determine backend availability; failing checks
cause HAProxy to mark backends as unavailable.

**Symptom:** HAProxy marks all backends as DOWN in the statistics interface.

**Solution:**

Check the Patroni service status on each backend node:

```bash
sudo systemctl status patroni
```

Test the Patroni REST API manually to verify health check responses:

```bash
curl http://pg-node:8008/
curl http://pg-node:8008/replica
```

Verify network connectivity between HAProxy and the backend nodes:

```bash
telnet pg-node 8008
```

Ensure the firewall allows traffic on port 8008:

```bash
# RHEL
sudo firewall-cmd --list-all

# Debian
sudo ufw status
```

## Cannot Connect Through HAProxy

Connection failures through HAProxy may indicate backend unavailability,
network issues, or listener configuration problems.

**Symptom:** Database connections to HAProxy fail with connection refused or 
timeout errors.

**Solution:**

Check the HAProxy statistics page for backend status:

```bash
curl http://haproxy-host:7000/
```

Verify that at least one backend node shows an UP status. Test a direct
connection to a backend node to isolate the problem:

```bash
psql -h pg-node -p 5432 -U admin
```

Confirm that HAProxy listens on the expected ports:

```bash
sudo netstat -tlnp | grep haproxy
```

## Connections Route to Wrong Node

Incorrect routing occurs when HAProxy sends connections to replica nodes
instead of the primary node.

**Symptom:** HAProxy routes write connections to a replica instead of the 
primary node.

**Solution:**

Check the current Patroni cluster status to identify the primary node:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yaml list
```

- Verify that the HAProxy configuration specifies the correct health check
  endpoints for primary detection.
- Ensure the Patroni REST API responds correctly on each backend node.
- Review the HAProxy configuration to confirm the health check paths match
  Patroni expectations.
