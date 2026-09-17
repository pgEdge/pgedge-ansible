# recover_cluster

The `recover_cluster` role rebuilds an existing pgEdge cluster from a PgBackRest
repository. It restores one zone from its repository and refills every other
zone across Spock from the restored one, so that every zone comes back holding
the same data.

See [Recovering a Cluster from Backup](../recovery.md) for the full procedure,
its prerequisites, and its parameters. This page describes the role itself.

!!! danger "This role destroys data"
    The role stops Patroni on every pgEdge node and erases every data directory
    in the cluster. Anything written after the recovery point is gone, in every
    zone.

## How the Role Is Applied

Unlike every other role in this collection, `recover_cluster` is applied one
task file at a time rather than as a whole role. Its steps run on different
hosts in a fixed order, with plays between them: every node stopped before any
node is erased, one node restored and cleaned before any other zone is rebuilt,
every zone rebuilt before the mesh is rewired. Applying it the ordinary way
would run every step on every host at once, so the role's `main.yaml` refuses
and says so.

Use the playbook in `sample-playbooks/recover-cluster/`, which applies the task
files in order:

| Task file | Applies to | Purpose |
|-----------|-----------|---------|
| `validate` | every pgEdge node | Check the request before anything is touched. |
| `quiesce` | every pgEdge node | Stop and disable Patroni and Postgres cluster-wide. |
| `reset_dcs` | every pgEdge node | Optional. Rebuild the zone's etcd cluster from nothing, for when the store itself is what is broken. |
| `clear_dcs` | each zone's first node | Remove the zone's cluster from the Patroni configuration store, and confirm it is gone. Skipped when the store was reset. |
| `wipe_data` | every pgEdge node | Erase and recreate the data directory. |
| `restore_leader` | `recovery_node` | Start Patroni so it restores the node from the repository, and wait for it to take the leader. |
| `clean_spock` | `recovery_node` | Remove the replication metadata the restore brought back, and verify it is gone. |
| `rebuild_zone` | each other zone's first node | Rebuild the zone's leader as an empty cluster. |
| `rehydrate` | each other zone's first node | Copy the restored zone's schema and data, and wait for the copy. |
| `rebuild_replicas` | every non-leader node | Rebuild each replica from its own zone's leader. |
| `upgrade_stanza` | each rebuilt zone's repository host | Record the zone's new cluster in its stanza so it can archive again. |

Each task file decides for itself which hosts it concerns. None of those
conditions can be written in the playbook, because they read role variables and
an `include_role` does not export those to the play that included it.

## Role Dependencies

- `role_config` provides shared configuration variables to the role.
- `setup_patroni` renders the Patroni configuration, including the PgBackRest
  bootstrap method the restored node bootstraps through.
- `setup_postgres` and `setup_pgedge` rebuild and rewire the zones that are not
  restored.
- `setup_backrest` must already have configured PgBackRest on the nodes, which
  an existing deployment will have done.

## Why Only One Zone Is Restored

Each zone keeps its own stanza describing its own physical cluster, and a stanza
restores to its own moment. Zones restored separately have no common position to
replicate forward from: the subscriptions between them would resume against data
neither side agrees on, and Spock would carry the disagreement forward rather
than report it. Restoring one zone and copying it gives every zone the same
starting state.

The copy is the one subscription in this collection created with
`synchronize_structure` and `synchronize_data`. Everywhere else a subscription is
created between nodes that are both empty and only has to stream forward from
the moment it exists, which is why `setup_pgedge` takes Spock's defaults and
synchronizes nothing.

## Why the Spock Metadata Is Removed

A restored node comes back with the Spock catalog it had when the backup was
taken: a node entry for every zone, a subscription to each of them, and a
replication origin per subscription recording how far this node had applied from
each of those zones.

Every one of those zones is then rebuilt from an empty data directory, so their
LSNs start again from the beginning. An origin left in place claims the restored
node has already applied everything up to a position the rebuilt zone will not
reach for a long time, and the subscription that reuses it resumes from there:
the rebuilt zone's changes are acknowledged without ever being applied. Nothing
reports it — the zones simply disagree, and go on disagreeing.

The role therefore drops every subscription, every node entry but its own, and
every replication origin that is not PostgreSQL's own, and then checks that they
are gone rather than assuming. Each of those statements is a loop over a catalog
that reports nothing when it removes nothing, so a drop that failed quietly
would look exactly like a catalog that was already clean.

## Why the Rebuilt Zones' Stanzas Are Upgraded

Only the restored zone comes back as the cluster its repository describes. Every
other zone is rebuilt from an empty data directory, so it carries a system
identifier its own stanza has never seen, and PgBackRest would refuse to archive
there — correctly, since as far as the repository knows this is some other
cluster. The zone would finish the recovery unable to back itself up, with
nothing saying so until the nightly job failed.

`pgbackrest stanza-upgrade` records the new cluster as another entry in the
stanza's history rather than replacing what is there, so the zone archives again
immediately and its earlier backups stay in the repository. Those backups are
historical from that point on: they describe a cluster that no longer exists, at
a position the recovery deliberately moved away from, so restoring one would
resurrect the divergence the recovery just undid.

## Idempotency

This role is **not** idempotent, and is not meant to be: it erases data
directories and rebuilds them.

It is, however, safe to re-run from any state a failed attempt left behind.
Every step before the restore erases or replaces what came before it — services
are stopped wherever they exist, the cluster is removed from the store if it is
there, and every data directory goes whatever state it is in — so a second run
starts over from the repository rather than resuming. That is the property
worth having, because the repository is the thing a recovery did not damage.

The one state it cannot start from is a configuration store it cannot read. It
refuses to erase anything it has not first proved it removed, which is why a
store that has lost quorum stops the recovery rather than letting it wipe the
cluster and then wait forever for a leader whose key is still there.
`recovery_reset_dcs` is the way out: it rebuilds the store instead of reading
it.
