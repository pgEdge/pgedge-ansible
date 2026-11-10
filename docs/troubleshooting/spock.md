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

## Run Stops Because a Zone Is Not Yet Part of the Cluster

**Symptom:** A deployment run stops in `setup_pgedge` with a message that a
zone is not yet part of this cluster, which already holds data, and that
nothing has been created in Spock.

**Solution:** The inventory lists a zone that has no Spock node in a database
that holds data on the other zones. An ordinary run would subscribe it without
copying that data, so it stops instead. If you are adding the zone, run again
with `-e pgedge_join_zones=<zone>`, as described in
[Adding a Zone to a Running Cluster](../add_zone.md). If the zone was removed
with `remove_zone`, or added by mistake, take its hosts out of the inventory.

The earlier roles in the run have already built the zone's hosts and created
its empty databases. Nothing in Spock has changed.

## Run Stops on pgedge_join_zones

**Symptom:** A run with `pgedge_join_zones` stops before the join, in
`setup_pgedge`.

**Solution:** The message says which of the following applies:

- **A listed zone is not a zone of this inventory.** Add the zone's hosts to
  the inventory, or correct the list. A list written in brackets as a plain
  argument, such as `-e pgedge_join_zones=[4]`, arrives as text and is
  reported here; use `-e pgedge_join_zones=4`, `=4,5`, or a JSON argument.
- **There is no running cluster to join.** No database in `db_names` holds
  data on any zone yet. A new cluster is built by an ordinary run: run again
  without the flag.
- **A database is in `db_names` but not yet in Spock on any zone.** Adding a
  database and joining a zone are separate changes. Run once without the flag
  to add the database to the existing zones, then again with it, or leave the
  database out of `db_names` until the join is done.
- **A zone that is not yet a member is not listed.** Every zone outside a
  cluster that holds data has to join it. Add the zone to the list, or take it
  out of the inventory.
- **`pgedge_join_zones` and `pgedge_seed_zone` are both given.**
  `pgedge_seed_zone` is for recovery only. Run again with only
  `pgedge_join_zones`.

## Run Stops Because the Zones Are Not One Cluster

**Symptom:** A run stops with a message that the zones with a Spock node are
not one cluster with at most one zone joining it, and lists missing
subscriptions.

**Solution:** In a database that holds data, every zone subscribes to every
other one, and only a single zone may be partway through a join. The listed
subscriptions were dropped, or never created, outside the collection. Create
the missing subscriptions, or remove the zone that is out of step with
[`remove_zone`](../roles/remove_zone.md), and run again.

## Join Refuses an Older Spock

**Symptom:** A join stops before it changes anything, with a message that a
zone runs a Spock older than 5.0.9, or that the joining zone runs an older
Spock than a member.

**Solution:** A join needs Spock 5.0.9 or later in every database on every
zone, and the joining zone may not run an older release than any member.
Running the deployment again doesn't upgrade Spock on a zone that is already
built. Upgrade the zone's packages, restart its Postgres one node at a time,
and run `ALTER EXTENSION spock UPDATE` in each database, then run the join
again.

## Join Refuses Because Pools Are Too Small

**Symptom:** A join stops before it changes anything, with a message that
`max_worker_processes`, `max_replication_slots`, `max_wal_senders` or
`max_active_replication_origins` is below what a zone needs, or has a change
waiting for a restart.

**Solution:** A new zone raises these pools on every zone, and they take
effect only on restart. With `pg_allow_restart: false`, the run configures
the new sizes but doesn't restart. Restart the zones the message names, one
node at a time (on Ultra-HA, with `patronictl restart`), then run the same
command again.

## Join Refuses Because a Subscription Is Not Replicating

**Symptom:** A join stops before it changes anything, with a message that a
subscription among the members is disabled or not `replicating`.

**Solution:** A join waits for bookmarks to pass between the existing zones,
so every subscription among them must replicate. Find the cause in that zone's
Postgres log and `spock.exception_status`, fix it, and enable the
subscription again:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT spock.sub_enable('sub_n2_n1', true);"
```

Then run the join again.

## A Join Stopped Partway

**Symptom:** A join fails with a message that the zone did not finish
joining a database, that the join can be resumed, and a list of replication
slots with the WAL each holds.

**Solution:** Fix the cause the message gives and run the same command again;
the join carries on from where it stopped. Until then, each slot listed keeps
WAL on its zone, and the amount grows with every write. If you won't resume
soon, release the slots: run [`remove_zone`](../roles/remove_zone.md) for the
joining zone, or drop each slot with the command the message gives, on the
zone that holds it. The join then has to start again from the beginning. See
[When a Join Stops](../add_zone.md#when-a-join-stops).

## A Join Cannot Be Resumed

**Symptom:** A join fails with a message that the zone cannot finish joining
a database and the join cannot be resumed.

**Solution:** The copy failed after it started, a slot the join needed is
gone, or the joining zone held tables or subscriptions the join didn't
create. The join has already dropped what it held on the other zones for that
database. Run the `remove_zone` playbook with
`-e remove_zone=<zone> -e remove_zone_confirm=true` to reset the joining zone,
then run the deployment again with `-e pgedge_join_zones=<zone>`.

## Joined Zone's Replication Sets Differ

**Symptom:** A join finishes, but reports that the joining zone's replication
sets differ from its source zone's.

**Solution:** The join adds the source's replication sets and tables to the
new zone, but never removes anything, and doesn't change the column list or
row filter of a table the new zone already has in a set. A table the source
added to or removed from a set while the join ran shows up here too. Make the
same change on the new zone with `spock.repset_add_table()` or
`spock.repset_remove_table()`.
