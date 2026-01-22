# Spock Replication

Spock enables advanced Postgres-to-Postgres replication capabilities that
power pgEdge's multi-region synchronization features. Problems with Spock
configuration can lead to failed synchronization, increasing replication lag,
or complete subscription errors.

Troubleshooting Spock requires understanding replication status, connection
authentication, proxy configuration, and conflict resolution mechanisms. This
section provides detailed guidance for diagnosing and resolving Spock-specific
issues that impact data synchronization across distributed Postgres instances
in your pgEdge deployment.

## Spock Node Creation Fails

Node creation failures typically result from missing extensions, permission
issues, or database connectivity problems.

**Symptom:** The Spock node creation command fails with an extension or 
permission error.

**Solution:**

Check that the Spock extension exists in the target database:

```bash
sudo -u postgres psql -d dbname -c "\dx spock"
```

- Verify that Postgres runs and accepts connections on the target host.
- Ensure that the `pgedge_user` exists and has the necessary permissions.
- Review the Postgres logs for detailed error messages.

## Subscription Creation Fails

Subscription failures occur when nodes cannot establish replication connections
due to network, authentication, or configuration issues.

**Symptom:** The Spock subscription creation command fails with a connection or 
authentication error.

**Solution:**

Test the connection from the local node to the remote node:

```bash
sudo -u postgres psql "host=remote-node user=pgedge dbname=demo port=5432"
```

- Ensure that `pg_hba.conf` on the remote node allows connections from the
  local node.
- Verify that the `pgedge_user` credentials match the remote configuration.
- Check network connectivity and firewall rules between the nodes.
- Review the `.pgpass` file to verify that the file contains the correct
  password.

## Proxy Connectivity Fails

Proxy connectivity issues prevent Spock from establishing replication through
HAProxy load balancers.

**Symptom:** Spock cannot connect to remote nodes through the HAProxy proxy.

**Solution:**

Check that HAProxy runs on the proxy host:

```bash
sudo systemctl status haproxy
```

Test HAProxy connectivity from the Spock node:

```bash
psql "host=haproxy-host port=5432 user=pgedge dbname=postgres"
```

- Verify the HAProxy configuration and health check settings.
- Ensure that Patroni runs on the backend Postgres nodes.
- Review HAProxy logs for connection errors or backend failures.

## Subscriptions Not Syncing

Synchronization issues occur when subscriptions establish but fail to replicate
data between nodes.

**Symptom:** The `sub_wait_for_sync()` function times out or hangs 
indefinitely.

**Solution:**

Query the subscription status to check the current state:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.subscription;"
```

- Verify that the `status` column displays `replicating` for active
  subscriptions.
- Review the Postgres logs for replication-related errors.
- Check network stability between the participating nodes.
- Look for table conflicts or constraint violations that may block
  replication.

## Replication Lag Increasing

Growing replication lag indicates that the subscriber cannot keep pace with
changes from the provider node.

**Symptom:** The replication lag between nodes increases continuously over 
time.

**Solution:**

Check the current replication status for all subscriptions:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.sub_show_status();"
```

Look for Spock worker exceptions that may indicate processing errors:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.exception_status;"
```

- Verify that sufficient network bandwidth exists between the nodes.
- Check for long-running transactions that may block replication.
- Review conflict resolution settings for appropriate behavior.
- Consider optimizing table designs or adding indexes to improve performance.

## Subscription Shows Disabled State

A disabled subscription indicates that Spock encountered an unrecoverable error
during replication.

**Symptom:** Spock marks the subscription as disabled and stops replicating 
data.

**Solution:**

Query the exception status to identify the root cause:

```bash
sudo -u postgres psql -d dbname -c "SELECT * FROM spock.exception_status;"
```

- Resolve the underlying exception that caused the subscription to disable.
- Re-enable the subscription manually after addressing the root cause.
- Review the `exception_behaviour` configuration setting to adjust automatic
  handling.
