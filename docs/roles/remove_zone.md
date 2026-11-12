# remove_zone

The `remove_zone` role detaches one zone from a running pgEdge cluster. Every
other zone forgets the zone in Spock, and, when the zone can be reached, the
zone's own subscriptions are dropped and its databases are reset, so that it
can [join the cluster](../add_zone.md) again from scratch or be retired.

The role performs the following tasks on inventory hosts:

- Refuse to start unless `remove_zone_confirm` is `true` and `remove_zone`
  names a zone of the inventory.
- Refuse when any other zone's primary cannot be reached or its Postgres is
  not running.
- Refuse when the zone holds the only complete copy of a database that holds
  data.
- On every other zone that subscribes to the zone, if the zone can be
  reached, wait until it has applied every write the zone has committed.
- For each database in `db_names` in turn: on every other zone's primary,
  drop the subscriptions from the zone; then on the zone's primary, if it can
  be reached, drop every subscription it has; then on every other zone's
  primary, drop the replication slots that served the zone, its Spock node,
  and the replication progress kept for it.
- On the zone's primary, if it can be reached, drop each database in
  `db_names` that holds a Spock node, a subscription or tables of its own.

The role leaves the following alone:

- The zone's hosts, its Postgres instance, Patroni, pgBouncer and anything
  else outside the databases in `db_names`. Erasing the hosts is up to you.
- Databases that are not in `db_names`, and roles.
- The inventory. The zone stays in it until you take it out.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

Use this role to take a zone out of a cluster, or to start a join over after
one that cannot be resumed. The join's failure message says when that is the
case; see [When a Join Stops](../add_zone.md#when-a-join-stops). It also
releases the replication slots a stopped join holds on the other zones, when
you decide not to resume it.

Apply it to the `pgedge` group with the inventory the cluster was deployed
with, with the zone still in that inventory. Don't gather facts in the play:
the zone may be down, and the role gathers facts itself on the hosts that
answer.

```yaml
- hosts: pgedge
  gather_facts: false
  collections:
    - pgedge.platform
  roles:
    - remove_zone
```

The `sample-playbooks/remove-zone` playbook does exactly this. Pass the zone
and the confirmation on the command line rather than writing them into an
inventory:

```bash
ansible-playbook playbook.yaml -i ../simple-cluster/inventory.yaml \
  -e remove_zone=3 -e remove_zone_confirm=true
```

Stop the applications that write to the zone before you run the role. The
role makes sure the other zones have every write the zone committed before it
starts, but a write that arrives after that point is dropped with the zone's
databases.

Afterwards, do one of the following:

- Take the zone's hosts out of the inventory.
- Join the zone again by running the deployment playbook with
  `-e pgedge_join_zones=3`. The deployment creates the zone's databases again
  before the join copies the cluster's data into them.

!!! warning "A Removed Zone Blocks Ordinary Runs"

    While the zone is still in the inventory, an ordinary deployment run
    stops before it changes anything in Spock. The run reports that the zone
    isn't part of the cluster and names `pgedge_join_zones`. The run does
    recreate the zone's empty databases before it stops.

## Configuration

This role uses the following parameters:

| Parameter | Use Case |
|-----------|----------|
| `remove_zone` | The number of the zone to remove (required). |
| `remove_zone_confirm` | Must be `true` for the role to do anything (default: `false`). |
| `remove_zone_wait_minutes` | How long to wait for each other zone to apply the zone's writes before anything is changed (default: `10`). |
| `db_names` | The databases the zone is removed from. |

## How It Works

Spock records a zone's membership on both sides. Each other zone has a
subscription from the zone, a replication slot that the zone's own
subscription reads from, and a row for the zone's node. The zone itself has
its node and a subscription from every other zone. The role removes all of
it, for every database in `db_names`, in three steps, after one check.

Before it changes anything, if the zone can be reached, the role makes sure
that no write the zone has committed is lost with it. In each database where
the zone has a node, it sets a bookmark in the zone's change stream with
`spock.sync_event()`, and waits until every other zone that subscribes to the
zone has applied the bookmark, as recorded in its `spock.progress`. That zone
then has every transaction the zone committed before the bookmark. A zone
that has not applied it within `remove_zone_wait_minutes`, for example
because its subscription from the zone is disabled, stops the run with
nothing changed.

1. On the zone, if it can be reached, the role drops every subscription.
   This stops the zone reading from the other zones, so the slots that served
   it fall idle.
2. On every other zone, the role drops the subscriptions whose provider is
   the zone's node. Spock's `sub_drop` also drops the replication origin that
   tracked each subscription, and the node row once no subscription names it.
   The role then drops the slot that served the zone's subscription, by the
   name Spock's `spock_gen_slot_name` gives it, then the node row if one is
   left. Last, it deletes the rows in `spock.progress` for the zone's node,
   which Spock never removes, so that a zone joined again under the same
   number does not start from its old position.
3. On the zone, if it can be reached, the role drops each database that
   holds a Spock node, a subscription or tables of its own, with
   `DROP DATABASE ... WITH (FORCE)`. A database that is already empty in that
   sense is left alone.

The second step never connects to the zone, so it works the same whether the
zone is running or not. The join in `setup_pgedge` runs this step alone,
through the role's `remaining_zones` entry point, to release the slots that a
join that cannot be resumed was holding.

### Zones That Cannot Be Reached

A zone counts as down when its primary doesn't answer, or answers with
Postgres not running. A zone that is down is still removed from every other zone, which is all the
cluster needs to carry on without it. Each subscription the role drops on the
other zones tries to drop its slot on the zone too, and waits up to Spock's
30-second connection timeout per subscription before warning that it could
not. Those slots are in the zone's own databases.

Nothing can confirm that the other zones received every write the zone made
before it went down. A write it committed that had not yet reached them is
not in the cluster after the removal, though it stays in the zone's own
databases until they are reset.

The zone's own databases keep their Spock configuration and data. If the zone
comes back while it is still in the inventory, run the role again to detach
and reset it as well. Otherwise, erase its hosts before using them again. A
zone that comes back with its old subscriptions finds the slots it read from
gone, and does not receive changes from the other zones.

### Replication Slots Still in Use

The role drops only slots that nothing is reading. A walsender can keep a slot
busy for a while after its subscriber has gone, until the connection closes or
`wal_sender_timeout` passes, so the role waits up to 150 seconds for each slot
to fall idle. A slot that is still in use after that stops the run with the
slot's name, zone, process and the WAL it holds. The subscriptions dropped
before that point stay dropped; run the role again once whatever is reading
the slot has stopped.

The same applies to the zone's own databases before they are dropped, since
Postgres doesn't drop a database while one of its slots is being read.

### The Only Copy of the Data

The role refuses to remove a reachable zone that holds the only complete copy
of a database with data in it. Another zone counts as holding a complete copy
when it has its own Spock node and tables of its own, isn't still copying
them, and either subscribes to the zone and is subscribed to by it, or no
longer subscribes to it at all. The second case covers a zone that an earlier
run removed while it was down and that has since come back. A zone that is
still joining from the zone being removed doesn't count. To take down the
whole cluster, use [`wipe_cluster`](wipe_cluster.md) instead.

### Ultra-HA Clusters

In an Ultra-HA cluster, the role finds each zone's primary through Patroni
and makes every change there. The replicas follow through physical
replication, and Spock's slot synchronization removes the dropped slots from
them, as long as `spock.drop_extra_slots` keeps its default of `on`. The zone counts as reachable when its primary is.
The role only asks Patroni which node leads each zone. It never starts
Patroni, so a zone whose Patroni is stopped on every node has no primary: the
zone being removed is then treated as one that cannot be reached, and any
other zone stops the run.

## Idempotency

This role is safe to re-run. Every step selects only what is still there, so
a run that stopped partway picks up where it left off, and a second run
changes nothing, including after a deployment run has recreated the zone's
empty databases.
