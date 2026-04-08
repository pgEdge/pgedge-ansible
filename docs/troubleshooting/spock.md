# Spock Replication Issues

This page covers [Spock](https://docs.pgedge.com/spock-v5/v5-0-6/) replication
issues.

## Subscription Creation Fails

**Symptom:** The Spock subscription creation command fails with a connection
or authentication error.

**Solution:** Test the connection from the local node to the remote node:

```bash
sudo -u postgres psql \
  "host=remote-node user=pgedge dbname=demo port=5432"
```

Verify that `pg_hba.conf` on the remote node allows connections from the
local node and that the `pgedge_user` credentials match.

## Subscriptions Not Syncing

**Symptom:** Subscriptions show as established but data does not replicate.

**Solution:** Query the subscription status:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.subscription;"
```

Check that the `status` column shows `replicating` for active subscriptions.
Review the Postgres logs for replication-related errors and check for table
constraint violations that may block replication.

## Replication Lag Increasing

**Symptom:** Replication lag between nodes grows continuously.

**Solution:** Check subscription status and exception history:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.sub_show_status();"
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.exception_status;"
```

Look for long-running transactions that block replication and verify that
sufficient bandwidth exists between zones.

## Subscription Shows Disabled State

**Symptom:** Spock marks a subscription as disabled and stops replicating.

**Solution:** Query the exception status to identify the root cause:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.exception_status;"
```

Resolve the underlying exception, then re-enable the subscription manually.
Adjust the `exception_behaviour` parameter if automatic handling is not
suitable.
