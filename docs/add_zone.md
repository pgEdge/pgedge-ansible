# Adding a Zone to a Running Cluster

This page describes how to add a zone to a pgEdge cluster that already holds
data, on a simple cluster or an Ultra-HA one. The new zone receives a copy of
every database in `db_names`, and then every write that any other zone makes.
The existing zones keep taking writes while the data is copied. Before the
copy, the run may restart each existing zone, one node at a time, to enlarge
its worker and replication pools; see
[Larger Pools on Every Zone](#larger-pools-on-every-zone).

Adding a zone has two steps:

1. Add the zone's hosts to the inventory.
2. Run the deployment playbook with `-e pgedge_join_zones=<zone>`.

The second step builds the zone like any other and then *joins* it to the
cluster. The join copies the existing zones' data and makes sure that no
write is lost or applied twice along the way. A join that stops partway
resumes when you run the same command again.

!!! warning "Applications Must Wait for the Join"

    Don't send application traffic to the new zone until the run that joins it
    has finished. Until then the zone is missing data, and anything written to
    it may not reach the other zones. Point applications at the zone only once
    the run reports that it is a member of every database.

!!! warning "One Major Change per Run"

    Only modify one major aspect of the cluster at a time. New replicas, new
    databases, new zones, and similar changes should not be mixed in a single
    run. Each is tested on its own, and a run that combines them takes paths
    that were not. The collection enforces this for databases: a run with
    `pgedge_join_zones` refuses a database that was newly added to `db_names`.
    Add the database in one run, without the flag, and join the zone in the
    next.

## Before You Start

Check the following before running the join:

- **Spock 5.0.9 or later on every zone.** The join uses Spock features that
  first appeared in 5.0.9, and checks the version in every database on every
  zone before it changes anything. Running the deployment playbook again does
  not upgrade Spock on zones that are already built: `install_pgedge` installs
  the newest packages when it first builds a node and leaves them alone after
  that. Upgrade any zone running an older Spock by hand before the join, as
  the Spock documentation describes: upgrade the packages, restart Postgres
  one node at a time, and run `ALTER EXTENSION spock UPDATE` in each
  database. The new zone may run a newer Spock than the existing zones, but
  not an older major or minor release: a zone on 5.0 cannot join members on
  6.0. The
  join compares only those two parts, so a zone on 5.0.9 can join members on
  5.0.13.
- **All existing zones replicating.** Every subscription between the existing
  zones must be enabled and `replicating`. The join waits up to five minutes
  for this, since the same run may have just restarted them, and then refuses
  to start.
- **Room in the worker and slot pools.** See
  [Larger Pools on Every Zone](#larger-pools-on-every-zone).
- **No other changes in the inventory.** Leave `db_names`, the other zones'
  hosts, and the rest of the configuration as they were for the last run.
- **A zone that was a member before is removed first.** To join a zone whose
  hosts were rebuilt, or whose databases were dropped, after it was part of
  the cluster, first run [`remove_zone`](roles/remove_zone.md) for it. Until
  then, the other zones still subscribe to the old zone, and the join refuses
  to start, naming those subscriptions.
- **Schema changes are replicated, but keep them few.** Data writes are
  expected and safe. With AutoDDL on, which is the default, a table created
  on any zone while the join runs reaches the new zone too. Because those
  tables arrive after the copy, the join's replication-set check can report
  them as present on only one zone. That report is expected, and the sets
  match once the join finishes. Hold large or destructive schema changes
  until the join has finished.

Only the databases in `db_names` are copied. Databases in
`unmanaged_db_names`, ColdFront's database when it is not in `db_names`, and
any other database on the existing zones are not part of the join.

## Adding the Zone to the Inventory

Give the new zone a zone number that no other zone uses, and add its hosts the
way the existing zones' hosts are listed.

On a simple cluster, a zone is one node. The following example adds zone 4 to
a three-zone cluster:

```yaml
pgedge:
  vars:
    db_password: secret
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3
    192.168.6.13:
      zone: 4
```

On an Ultra-HA cluster, a zone has its pgEdge nodes and, usually, an HAProxy
node, and optionally a backup server. The following example adds zone 3 to a
two-zone cluster:

```yaml
pgedge:
  hosts:
    # ... zones 1 and 2 as before ...
    192.168.6.24:
      zone: 3
    192.168.6.25:
      zone: 3

haproxy:
  hosts:
    # ... zones 1 and 2 as before ...
    192.168.6.26:
      zone: 3
```

## Running the Join

Run the deployment playbook you deployed the cluster with, against the whole
inventory, and name the zone in `pgedge_join_zones`:

```bash
ansible-playbook -i inventory.yaml playbook.yaml -e pgedge_join_zones=4
```

To join more than one zone in a run, separate the numbers with commas, or pass
a JSON list. Zones join one at a time, in the order given:

```bash
ansible-playbook -i inventory.yaml playbook.yaml -e pgedge_join_zones=4,5
ansible-playbook -i inventory.yaml playbook.yaml -e '{"pgedge_join_zones": [4, 5]}'
```

Don't write the list in brackets as a plain argument: Ansible passes
`-e pgedge_join_zones=[4]` as the text `[4]`, and the run stops at once with
"Validation of arguments failed", since `[4]` is not a zone number. Pass the setting on the command line rather than in the
inventory, where it would sit waiting for the next unrelated run. Leaving it
on a later run does no harm: a zone that is already a member is reported and
skipped.

Use `pgedge_join_zones` only to add a zone to a cluster that already holds
data. A new cluster is built by an ordinary run, and a run with the flag
refuses to start when no database holds data yet.

### What Happens

The run builds the new zone exactly as a deployment would: packages,
Postgres, and on Ultra-HA, etcd, Patroni and HAProxy. It also sizes the pools
on every existing zone for the larger cluster. Then `setup_pgedge` classifies
every zone in every database, checks that the join can go ahead, and joins
each zone in turn. For each database, in `db_names` order, the join does the
following:

1. Copies the roles of an existing zone, the *source*, to the new zone, once
   for the whole zone, so that the copied tables have their owners.
2. Creates the new zone's Spock node.
3. On every other existing zone, creates a replication slot for the new zone,
   which keeps every write that zone makes from then on.
4. Waits until the source has applied everything the other zones wrote
   before their slots began.
5. Copies the source's schema and data to the new zone through a Spock
   subscription that then goes on replicating from the source.
6. Waits for the new zone to apply what the source committed during the
   copy.
7. Moves each other zone's slot to the last of its writes that the copy
   already holds, so that the new zone receives each later write once.
8. Matches the new zone's replication sets to the source's, then starts the
   new zone's subscriptions from the other zones and waits for them to catch
   up.
9. Subscribes every existing zone to the new zone.
10. Exchanges a bookmark both ways with every zone and checks that the new
    zone is a member.

The source is the lowest-numbered existing zone; a resumed join keeps the
source it started with. On Ultra-HA, every step runs
on each zone's current primary, and the new zone's replicas follow its
primary through physical replication. When it finishes a database, the run
reports:

```text
Zone 4 is a member of demo: it copied zone 1, and replicates with zones 1, 2, 3 both ways.
```

### How Long It Takes

The copy in step 5 takes most of the time, and it takes as long as the
database is large: Spock copies every row and then builds every index on the
new zone. The other steps normally take seconds each. No fixed time limit
applies to the copy. The run gives up on it only when nothing has moved for
`pgedge_seed_stall_minutes` (15 by default), or after `pgedge_seed_max_hours`
(24 by default), each counted per database. Every other wait in the join is
limited by `pgedge_join_wait_minutes` (30 by default). See
[Spock Configuration](configuration/spock.md).

While the copy runs, the task
`Wait for this zone to finish copying zone 1` stays open. To watch the
copy, connect to the new zone's primary:

```bash
sudo -u postgres psql -d demo \
  -c "SELECT * FROM spock.sub_show_status();" \
  -c "SELECT * FROM spock.local_sync_status;" \
  -c "SELECT * FROM pg_stat_progress_copy;"
```

To see the slots the join holds on an existing zone, and how much WAL each
keeps, run this on that zone's primary:

```bash
sudo -u postgres psql -d demo -c "
  SELECT slot_name, active,
         pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn))
    FROM pg_replication_slots;"
```

### Effects on the Existing Zones

The existing zones keep taking reads and writes throughout the join itself,
apart from the restarts for larger pools described above, which come before
it. The join changes them in the following ways:

- **Held WAL.** Each slot the join creates keeps WAL on its zone until the new
  zone reads it. The slots keep WAL from step 3 until the new zone starts
  reading them in step 8, so the WAL each holds grows with the write rate and
  the time the copy takes. Make sure each zone has disk space for the writes it takes
  while the largest database is copied.
- **A brief pause on the source.** When each database's copy starts, the
  source zone's Spock apply workers pause, so that the copy's snapshot and the
  positions the join records agree exactly. The pause lasts a few seconds,
  and Spock releases the workers after `spock.pause_timeout` (10 seconds by
  default) in any case. The source keeps taking its own writes during the
  pause; only applying the other zones' writes on the source waits, and it
  catches up afterwards. If the workers cannot all be paused within
  `spock.pause_timeout`, the join says so and goes on. Then, or if the
  workers are released before the copy's snapshot starts, writes the source
  applied from the other zones in between may reach the new zone twice: once
  in the copy and again by replication. On a table with a primary key or
  unique index, Spock resolves the second as a conflict and logs it in
  `spock.resolutions`. On a table with neither, it becomes an extra row on
  the new zone, so check such tables for duplicate rows after the join.
- **Load on the source.** The copy reads every table on the source zone, and
  its snapshot holds back vacuum there until the data is copied.

### Larger Pools on Every Zone

Every zone needs background workers, replication slots and WAL senders for
each other zone, and on Postgres 18 and later replication origins too, so a
new zone raises those pools on **every** zone. The run calculates the new
sizes as described in
[Worker and Replication Sizing](configuration/postgres.md#worker-and-replication-sizing),
writes them, and restarts each zone one node at a time to apply them, before
the join starts. Applications on those zones see the restart as they would
any other.

With `pg_allow_restart: false`, the run writes the new sizes but leaves the
restarts to you, and the join refuses to start, naming each zone and pool that
is still too small. Restart those zones, one node at a time, then run the same
command again. If you set any of these pools in `pg_parameters`, recalculate
them for the larger cluster first; `init_server` refuses a value below what
the cluster needs.

## When a Join Stops

A join that stops partway can almost always be resumed. Every step asks the
cluster whether it is already done, and the only thing the join records is
that it has not finished: the setting `pgedge.join_pending` on each database
the zone is joining, set before anything is created there and cleared once
the zone replicates with every member both ways. It keeps a join that stopped
in its last steps, when every subscription already exists, from being taken
for a finished one. So you can stop a run at any point, or let it fail, and
then run the same command again. Zones that finished in an earlier run are skipped, and the
zone that was joining carries on from where it stopped.

### A Join That Can Be Resumed

When a join fails in a way it can resume from, it keeps everything it has
created, because the slots on the other zones are what let the new zone
receive every write it has not yet seen. The failure names the zone, the
database and the step, and lists each slot the join holds with the WAL it
keeps:

```text
Zone 4 did not finish joining demo. It failed at "...": ... This can be
resumed: run the same command again, with -e pgedge_join_zones=4, and the join
carries on from where it stopped. Until then the join holds these replication
slots, and each keeps WAL on its zone until it is read or dropped: <slot> on
zone 2 (192.168.6.11), holding 1204 MB; <slot> on zone 3 (192.168.6.12),
holding 1187 MB. If you are not resuming soon, release them by running the
remove_zone playbook with -e remove_zone=4 -e remove_zone_confirm=true, ...
or by dropping them as postgres on each zone's primary: on 192.168.6.11,
psql -d demo -c "SELECT pg_drop_replication_slot('<slot>')"; ...
```

Fix the cause the message gives, and run the same command again soon. Until
then, each slot keeps WAL on its zone and the amount grows with every write.
If you can't resume before disk space becomes a concern, give up the join:
run [`remove_zone`](roles/remove_zone.md) for the new zone, which drops the
slots and resets the zone, or drop the slots with the commands the message
gives. Either way, the join then has to start again from the beginning.

!!! warning "A Stopped Join Holds WAL on the Existing Zones"

    Each replication slot a stopped join holds keeps every WAL file its zone
    writes from then on. Left long enough, it fills the zone's disk. Resume
    the join, or release the slots, rather than leaving it.

### A Join That Cannot Be Resumed

A few failures leave nothing a rerun can continue from:

- The copy failed after it started. Spock does not resume a copy that stopped
  while creating the schema, copying rows, or building constraints, or one
  it disabled.
- A slot the join needs is gone, for example after it was dropped by hand.
- The new zone holds tables or subscriptions that the join did not create,
  so its databases were not empty when it started.

The join then releases what it held: it drops the new zone's subscriptions in
that database, and on every other zone it drops the slots, subscriptions and
node it held for the new zone. The failure says which, and gives the commands
for starting again:

```text
Zone 4 cannot finish joining demo, and the join cannot be resumed: ...
Run the remove_zone playbook with -e remove_zone=4 -e remove_zone_confirm=true
to reset zone 4, then run this again with -e pgedge_join_zones=4 to join it
from the beginning.
```

Run [`remove_zone`](roles/remove_zone.md) as the message says. It resets the
new zone's databases, which the next deployment run creates again empty. Then
run the deployment with `-e pgedge_join_zones` again.

## Why an Ordinary Run Refuses a New Zone

A zone added to the inventory of a running cluster doesn't join it by itself.
The subscriptions an ordinary deployment creates stream changes from the
moment they exist and copy nothing written before, so the new zone would start
without the data the others hold and disagree with them from then on.

So, before `setup_pgedge` creates anything in Spock, it reads every zone's
Spock state in every database in `db_names`. A database holds data when some
zone has its Spock node there and tables of its own. A zone without a node in
such a database is not yet part of the cluster, and an ordinary run stops
before it changes anything in Spock:

```text
Zone 4 is not yet part of this cluster, which already holds data in demo. An
ordinary run would subscribe it without copying that data, and the zones would
disagree from then on, so nothing has been created in Spock. To join it, run
this again with -e pgedge_join_zones=4.
```

The refusal comes late in the run, from `setup_pgedge`. By then the earlier
roles have built the new zone's hosts and created its empty databases, and
may have restarted the existing zones into larger pools. Nothing in Spock has
changed. Either run again with `pgedge_join_zones`, or take the zone's hosts
out of the inventory.

The flag can only start a join for a zone that needs one. A zone joins only
when it is both missing from the cluster and named in `pgedge_join_zones`, so
a typo in the inventory can't start a join nobody asked for. The following
table lists what the run does in each case:

| Cluster | Without `pgedge_join_zones` | With `pgedge_join_zones` |
|---------|-----------------------------|--------------------------|
| No database holds data yet | Builds the cluster as a new one. | Refuses: there is no cluster to join. |
| Every zone is a member | Changes nothing in Spock. | Reports the listed zones as members and skips them. |
| A zone is not yet a member | Refuses, naming the zone and the flag. | Joins the listed zones; refuses if a zone that isn't a member is not listed. |
| `db_names` has a database no zone has in Spock yet | Adds the database to Spock on every zone. | Refuses: add the database first, in a run without the flag. |

A listed zone that is not in the inventory is refused in every case.

## Joins and Recovery

`pgedge_seed_zone` is a different mechanism, for recovery only. The
[recovery playbook](recovery.md) sets it after restoring one zone from backup,
while every other zone is empty and takes no writes, so the empty zones can
copy the restored zone without accounting for writes elsewhere. Don't use it to
add a zone to a running cluster; use `pgedge_join_zones`. The run refuses the
two together.
