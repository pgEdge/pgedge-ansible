# Recovering a Cluster from Backup

This page describes how to rebuild an existing pgEdge cluster from a PgBackRest
repository, either to the latest point the repository holds or to a moment in
the past. The procedure is an intervention on a cluster that already exists and
already has backups, not a way to deploy a new one.

!!! danger "This procedure destroys data"
    Recovery stops Patroni on every pgEdge node, erases every data directory in
    the cluster, and rebuilds the cluster from the backup repository of a single
    zone. Anything written after the recovery point is gone, in every zone. The
    playbook refuses to start unless `recovery_confirm` is set to `true`.

## What the Procedure Does

The collection restores **one zone** from its repository, and rebuilds every
other zone empty and refills it across Spock from the restored one.

This is deliberate. Each zone keeps its own stanza describing its own physical
cluster, and a stanza restores to its own moment. Zones restored separately have
no common position to replicate forward from: the subscriptions between them
would resume against data neither side agrees on, and the cluster would carry
the disagreement forward rather than report it. Restoring one zone and copying
it gives every zone the same starting state.

The procedure runs in this order:

1. Validate the request, then stop and disable Patroni and Postgres on every
   pgEdge node in every zone.
2. Remove each zone's cluster from the Patroni configuration store, and confirm
   it is gone.
3. Erase and recreate every pgEdge data directory.
4. Start Patroni on the node named by `recovery_node`. Its configuration carries
   a PgBackRest bootstrap method, so Patroni restores the node from the
   repository, replays WAL to the recovery target, and promotes it.
5. Strip the Spock metadata the restored node came back with — the other zones'
   node entries, every subscription, and the replication origins behind them.
6. Rebuild every other zone's leader as an empty cluster, exactly as a first
   deployment would.
7. Subscribe each rebuilt zone to the restored one with structure and data
   synchronization, and wait for the copy to finish.
8. Build the rest of the subscription mesh with `setup_pgedge`, then rebuild
   every replica from its own zone's leader.
9. Record each rebuilt zone's new cluster in its stanza with
   `pgbackrest stanza-upgrade`, so the zone can archive again.
10. Re-establish the backup schedule with `finalize_backrest`, which takes a backup
    only if the repository has none — so the recovery point survives the
    recovery.

## Rebuilding onto Replacement Hardware

The case where every pgEdge node is gone and only the repository survived — a
dedicated backup server that outlived the cluster, or an S3 bucket — is still a
recovery, not a deployment. Run both playbooks in order:

```bash
# 1. Install the software. This stops before it initializes any data directory,
#    because the repository already holds a cluster.
ansible-playbook -i inventory.yaml playbook.yaml

# 2. Restore into it.
ansible-playbook -i inventory.yaml recover-playbook.yaml \
  -e recovery_node=192.168.6.10 \
  -e recovery_confirm=true
```

The first run is expected to stop. `setup_postgres` asks the repository whether
it already holds a cluster before initializing anything, and refuses when it
does, naming the stanza and the number of backups it found. By that point every
package is installed and every configuration file is written, which is the state
the recovery playbook needs — so the stop is a handoff, not a failure to work
around.

!!! note "Why the deployment does not simply restore"
    Each zone keeps its own repository, restored to its own moment. A deployment
    that restored every zone from its own repository would produce zones holding
    different data with no common position to replicate forward from, and the
    subscriptions between them would carry that disagreement forward rather than
    report it. Only the recovery playbook knows to restore one zone and copy it
    to the others, which is why the deployment stops and hands over.

In SSH mode the check may not be able to reach the repository that early,
because the backup server has not yet authorized the new nodes' keys. The
deployment then proceeds, builds an empty cluster, and stops at `finalize_backrest`
instead — later and messier, but with the repository equally untouched. Both
checks refuse to write; neither can be talked into adding a backup to a
repository that already has one.

## Prerequisites

- The cluster is an HA cluster (`is_ha_cluster: true`). A cluster without
  Patroni has no bootstrap method to restore through and must be restored with
  `pgbackrest` directly.
- Every zone has a backup repository configured, so the rebuilt zones can
  archive once they are back.
- The repository holds at least one backup for the zone being restored, and the
  WAL needed to reach the target.
- `recovery_node` names the **first** pgEdge node of its zone as the inventory
  orders them. The collection treats a zone's first node as the one Patroni
  bootstraps and the one that carries the zone's Spock node.
- No application is writing to the cluster. The rebuilt zones are copied from
  the restored one, and a zone still taking writes during the copy has changes
  of its own that nothing will carry anywhere.

## Running a Recovery

Use the playbook in `sample-playbooks/recover-cluster/` with the same inventory
the cluster was deployed from. To restore everything the repository holds:

```bash
ansible-playbook -i inventory.yaml playbook.yaml \
  -e recovery_node=192.168.6.10 \
  -e recovery_confirm=true
```

To restore to a point in time instead:

```bash
ansible-playbook -i inventory.yaml playbook.yaml \
  -e recovery_node=192.168.6.10 \
  -e recovery_confirm=true \
  -e recovery_target_type=time \
  -e 'recovery_target=2026-09-15 14:30:00+00'
```

Pass these on the command line rather than writing them into an inventory, where
they would sit waiting for the next unrelated run.

How long the restore takes is a property of the database, not of this playbook,
so there is no fixed budget. The waiter watches PgBackRest's restore log,
`pg_control`'s timestamp and the size of the data directory, and gives up only
when none of them has moved for `recovery_stall_minutes`. A six-hour restore
succeeds untouched; one that has wedged is reported in fifteen minutes rather
than after a timeout drains. Progress is printed as it goes, so `-v` shows
movement.

The playbook reports the timeline and WAL position the restored cluster came
back to. Check it against the target that was asked for: when a target falls
outside what the repository can reach, PgBackRest stops at the last point it
could reach rather than failing.

## Recovery Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `recovery_confirm` | `false` | Must be `true` for the playbook to run at all. |
| `recovery_node` | (none) | The pgEdge node to restore from its repository, spelled as the inventory spells it. Must be the first node of its zone. |
| `recovery_target_type` | (none) | PgBackRest `--type`: `time`, `xid`, `lsn`, `name` or `immediate`. Unset restores everything the repository holds. |
| `recovery_target` | (none) | The value the target type stops at. Required for every type except `immediate`. |
| `recovery_backup_set` | (none) | A specific backup to restore, labelled as `pgbackrest info` labels it. Unset takes the latest backup that can reach the target. |
| `recovery_stall_minutes` | `15` | Give up only after the restore has made no progress for this long. There is no overall deadline: a restore that keeps moving is left alone however long it takes. |
| `recovery_poll_seconds` | `30` | How often to look. |
| `recovery_max_hours` | `24` | Backstop against a waiter that never returns. Not an expected duration. |
| `recovery_reset_dcs` | `false` | Rebuild the distributed configuration store from nothing instead of removing the cluster from it. For when the store itself is what is broken. |

## Running It Again

A recovery that fails partway can simply be run again. Every step before the
restore either erases or replaces what the previous attempt left: the cluster is
stopped wherever its services exist, removed from the store if it is there,
and every data directory is erased whatever state it is in. The second attempt
does not resume the first, it starts over from the repository — which is the
point, because the repository is the thing that was not damaged.

That holds for a failure at any stage. A recovery that got as far as restoring
one zone and then failed rebuilding another is not half-recovered in a way that
has to be unpicked; the next run erases the restored zone too and restores it
again.

Two things are worth knowing:

- The recovery needs the cluster's certificate authority. `setup_patroni` signs
  each rebuilt node's client certificate against it and never creates one, so
  without it the recovery fails with "The CA certificate file tls/etcd/ca.crt
  does not exist". Either copy the deployment's `tls/` directory next to the
  recovery playbook, or supply the authority from the inventory with
  `etcd_ca_cert` and `etcd_ca_key` — see
  [etcd Configuration](configuration/etcd.md), which is the more durable
  arrangement because that directory is gitignored and nothing recreates it.
- Postgres server certificates are the lesser half of the same point.
  `setup_postgres` stages them from a path resolved against the playbook's own
  location, so a recovery run without the deployment's `tls/` gives the rebuilt
  zones a freshly minted certificate while the restored zone keeps the one from
  its backup. Nothing verifies them, so this is untidy rather than broken.
- If the configuration store itself is what is broken — etcd that has lost
  quorum, keys nobody can remove — the ordinary path cannot start, because it
  refuses to erase anything it cannot first prove it removed. Re-run with
  `-e recovery_reset_dcs=true` and the store is rebuilt from nothing instead.
  Nothing of value lives there: Patroni keeps membership and the leader lock in
  it and rebuilds both from the bootstrap it is about to perform. This applies
  only to the etcd cluster the collection deploys itself; an external store has
  to be reset by whoever runs it.

## Recovering a Single Node

A node that lost its data directory, rather than a cluster that lost its data,
needs none of the above. Patroni rebuilds a replica on its own: erase the data
directory and start the Patroni service, and the node clones from its zone's
leader.

By default that clone is a `pg_basebackup` from the leader. Setting
`patroni_replica_from_backup: true` makes Patroni try a PgBackRest delta restore
first instead, which moves only the blocks that changed and reads from the
repository rather than from the leader. It is worth it for a large database, at
the cost of making replica creation depend on the repository being healthy;
`pg_basebackup` remains the fallback either way, because Patroni walks its list
of methods in order.

## What Happens to the Rebuilt Zones' Backups

Only the restored zone comes back as the cluster its repository describes. Every
other zone is rebuilt from an empty data directory and refilled across Spock, so
it carries a system identifier its own stanza has never seen, and PgBackRest
would refuse to archive there.

The recovery runs `pgbackrest stanza-upgrade` on those zones, which records the
new cluster as another entry in the stanza's history rather than replacing what
is there. The zone archives again immediately and its earlier backups stay in
the repository.

Those earlier backups are historical from that point on. They describe a cluster
that no longer exists, at a position the recovery deliberately moved away from,
so restoring one would resurrect the divergence the recovery just undid. The
existing retention settings expire them as new full backups accumulate; expire
them sooner by hand if the repository space matters.

## What a Recovery Leaves Behind

The Patroni configuration on the restored node keeps its PgBackRest bootstrap
method until `setup_patroni` is next applied without `recovery_node` set. The
section is inert — Patroni consults it only when it is genuinely bootstrapping a
cluster — but it will be rewritten by the next ordinary deployment run.

Snowflake node IDs, Spock node names and zone numbering are unchanged: the
restored zone keeps its identity, and the rebuilt zones are recreated with the
identities their inventory gives them.

## Why the Standard Playbook Is Safe to Re-run

The concern a recovery procedure raises is the opposite one: that redeploying a
cluster whose repository already holds backups would add an empty backup to it.
Under the default `full_backup_count: 1` that is not merely untidy — when a new
full backup completes, PgBackRest expires the previous full backup and the WAL
belonging to it, discarding the recovery point the cluster was about to be
restored from.

`finalize_backrest` asks the repository what it holds rather than inferring it from
where the role sits in the playbook. It creates the stanza only when the stanza
does not exist, and takes a full backup only when the stanza has none. It also
compares the cluster's system identifier against the one the stanza describes,
and stops if they disagree — which is what happens when an inventory names a
repository belonging to a different cluster, or when a data directory was
rebuilt where it should have been restored.
