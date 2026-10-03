# Recovering a Cluster from Backup

This page describes how to rebuild a pgEdge cluster from its PgBackRest
repositories, either to the latest point the repositories hold or to a moment
in the past. A recovery is a deployment that builds Postgres from a backup
instead of from nothing, so it runs the same way whether the hosts are the
cluster's own or freshly provisioned replacements.

A recovery has three steps, each a playbook:

1. **Wipe** the cluster with `sample-playbooks/wipe-cluster/playbook.yaml`,
   unless the hosts are new and hold no cluster.
2. **Recover** it with `sample-playbooks/ultra-ha-recover/playbook.yaml`. This
   step can be repeated, to another target or from another zone, until the
   result is right.
3. **Commit** to the result with
   `sample-playbooks/ultra-ha-recover/commit-restore.yaml`, which takes the
   backups the recovery did not and restores the backup schedule.

No step ever removes a backup. Only the commit adds one, and under the default
retention the commit is what expires the backups the recovery came from.

## What the Procedure Does

The recovery restores **one zone** from its repository: the zone of
`recovery_node`. Every other zone is built empty and copies the restored zone
across Spock.

This is deliberate. Each zone keeps its own stanza describing its own physical
cluster, and a stanza restores to its own moment. Zones restored separately have
no common position to replicate forward from: the subscriptions between them
would resume against data neither side agrees on, and the cluster would carry
the disagreement forward rather than report it. Restoring one zone and copying
it gives every zone the same starting state.

The recovery playbook is the Ultra-HA deployment playbook with
[`recover_postgres`](roles/recover_postgres.md) in place of `setup_postgres`,
and with the backup servers set up first. It runs in this order:

1. Install and configure everything a deployment does, up to Postgres.
2. Build every node's Postgres as `setup_postgres` would, then replace the
   cluster on `recovery_node` with a restore from its zone's repository.
   Postgres replays WAL to the target outside Patroni and promotes.
3. Strip the Spock metadata the restored node came back with: the other zones'
   node entries, every subscription, and the replication origins behind them.
4. Upgrade each zone's stanza with `pgbackrest stanza-upgrade` where it does not
   describe the cluster now in the zone, so every zone can archive from the
   moment Patroni starts it.
5. Start etcd and Patroni, which take over each zone's cluster and build its
   replicas, exactly as in a deployment.
6. Have every other zone copy the restored zone with `setup_pgedge`, through
   `pgedge_seed_zone`, and then build the rest of the subscription mesh.

## Prerequisites

- The cluster is an HA cluster (`is_ha_cluster: true`). A cluster without
  Patroni must be restored with `pgbackrest` directly.
- Every zone has a backup repository configured, so every zone can archive
  once it is back.
- Every SSH repository is on a host in the `backup` group. The recovery runs
  `pgbackrest stanza-upgrade` on that server, and a server named only by
  `backup_host` is outside the inventory. The recovery refuses a rebuilt zone
  whose repository is reached that way before it builds anything.
- The restored zone's repository holds at least one backup, and the WAL needed
  to reach the target.
- `recovery_node` names the **first** pgEdge node of its zone as the inventory
  orders them. A zone's first node is the one the rest of the zone is built
  from.
- No pgEdge node holds a cluster. Run `wipe_cluster` first on hosts that do.
- No application is writing to the cluster.

## Wiping the Cluster

[`wipe_cluster`](roles/wipe_cluster.md) stops Postgres, Patroni, pgBouncer and
the collection's etcd, removes the cluster from any other configuration store,
removes the scheduled backups, and erases the components' configuration and
data. It leaves every backup repository alone.

```bash
ansible-playbook -i inventory.yaml ../wipe-cluster/playbook.yaml \
  -e wipe_confirm=true
```

It refuses to wipe a cluster that no zone's repository holds a backup of.
Freshly provisioned hosts need no wipe, but a backup server that outlived the
cluster still runs the old backup schedule, so wiping is worth doing anyway: on
hosts with nothing to stop or erase, it only removes that schedule.

## Running a Recovery

Use the playbook in `sample-playbooks/ultra-ha-recover/` with the inventory the
cluster was deployed from. To restore everything the repository holds:

```bash
ansible-playbook -i inventory.yaml playbook.yaml \
  -e recovery_node=192.168.6.10
```

To restore to a point in time instead:

```bash
ansible-playbook -i inventory.yaml playbook.yaml \
  -e recovery_node=192.168.6.10 \
  -e recovery_target_type=time \
  -e "recovery_target='2026-09-15 14:30:00+00'"
```

The inner quotes around the target matter. Ansible splits a `key=value`
argument at its spaces, so `-e 'recovery_target=2026-09-15 14:30:00+00'` sets
the target to the date alone and quietly discards the time of day. The
recovery refuses a `time` target without one rather than restoring to
midnight.

Pass these on the command line rather than writing them into an inventory, where
they would sit waiting for the next unrelated run.

How long the replay takes is a property of the database, not of the playbook,
so there is no fixed budget. The role watches the restored node's log and its
`pg_control` timestamp, and gives up only when neither has moved for
`recovery_stall_minutes`, or at once if Postgres stops.

The playbook reports the timeline and WAL position the restored cluster came
back to. Check it against the target that was asked for: when a target falls
outside what the repository can reach, PgBackRest stops at the last point it
could reach rather than failing.

### Certificates

The deployment generated the etcd certificate authority and the Postgres
server certificate into a `tls/` directory beside its own playbook, and
collected the hosts' SSH keys into `host-keys/`. A recovery run from its own
directory generates new ones. That works, because the recovery rebuilds etcd
from nothing, but the next run of the deployment playbook from its own
directory would then find an etcd that trusts a different authority than its
`tls/` holds, and stop. Either copy the deployment's `tls/` and `host-keys/`
directories beside the recovery playbook before running it, or supply the
authority from the inventory with `etcd_ca_cert` and `etcd_ca_key`, as
[etcd Configuration](configuration/etcd.md) describes. The inventory is the
more durable arrangement, because it works from any controller.

## Recovery Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `recovery_node` | (none) | The pgEdge node to restore from its repository, spelled as the inventory spells it. Must be the first node of its zone. |
| `recovery_target_type` | (none) | PgBackRest `--type`: `time`, `xid`, `lsn`, `name` or `immediate`. Unset restores everything the repository holds. |
| `recovery_target` | (none) | The value the target type stops at. Required for `time`, `xid`, `lsn` and `name`; must be unset for `immediate` or no type. |
| `recovery_target_timeline` | (none) | PgBackRest `--target-timeline`. Unset follows the newest timeline. See [Trying Again](#trying-again). |
| `recovery_backup_set` | (none) | A specific backup to restore, labelled as `pgbackrest info` labels it. Unset takes the newest backup that can reach the target. |
| `recovery_stall_minutes` | `15` | Give up only after the restored node has made no progress for this long. |
| `recovery_poll_seconds` | `30` | How often to look. |
| `recovery_max_hours` | `24` | Hard ceiling on the restore, the replay, and each zone's Spock copy. Raise it for a restore or copy expected to run longer. |

## Trying Again

The recovery takes no backups and leaves the backup schedule off, so every
backup the repositories held before it is still there afterwards. Until the
recovery is committed, it can be run again as often as it takes: wipe the
cluster, then run the recovery playbook with a different target, or a
different `recovery_node`. A recovery that failed partway is retried the same
way. The wipe accepts the uncommitted cluster, because the restored zone still
holds the backups it came from.

Two things are worth knowing:

- A second point-in-time recovery to a **later** moment than the first has to
  name the timeline the first one started from with
  `recovery_target_timeline`. Each recovery that stops at a target starts a new
  timeline, and by default the next recovery follows the newest timeline, which
  is the one the first attempt created rather than the one the cluster was
  originally on. `pgbackrest info` and the timeline the first attempt reported
  give the number to use.
- Recovering from a zone an earlier, uncommitted recovery rebuilt works too.
  That zone's stanza was upgraded to describe the rebuilt cluster, but every
  backup of the original is still in it, and `recover_postgres` names the
  newest of them explicitly and upgrades the stanza back.

## Committing a Recovery

Once the recovered cluster is the one to keep, run the commit playbook beside
the recovery playbook:

```bash
ansible-playbook -i inventory.yaml commit-restore.yaml
```

It applies [`finalize_backrest`](roles/finalize_backrest.md), which takes a full
backup of each zone that has no backup it could restore the cluster from, and
installs the backup schedule again. That means every zone the recovery rebuilt,
because its stanza holds only backups of the cluster it replaced, and the
restored zone too after a point-in-time recovery, whose newest backups lie on
the timeline the recovery abandoned. After a recovery that replayed the whole
archive, the restored zone's backups remain valid and it takes none.

Under the default `full_backup_count` of 1, each of those backups expires the
ones before it. That is the point of committing: from then on the recovery
cannot be tried again from those backups.

To commit in the same run, for a recovery that will not be revisited, add
`finalize_backrest` at the end of the recovery playbook, as the deployment
playbook has it:

```yaml
- hosts: pgedge:backup
  collections:
  - pgedge.platform
  roles:
  - finalize_backrest
```

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
of methods in order. PgBackRest refuses to restore a backup of a cluster its
stanza no longer describes, so a replica in a zone a recovery rebuilt falls
back to `pg_basebackup` until that zone is committed.

## Why the Standard Playbook Is Safe to Re-run

Deploying onto hosts whose repositories already hold backups does not add an
empty backup to them. `setup_postgres` refuses to initialize a cluster beside a
repository that already describes one, and points here instead.
`finalize_backrest` asks the repository what it holds rather than inferring it
from where the role sits in the playbook: it creates the stanza only when the
stanza does not exist, and takes a full backup only when the stanza has no
backup it could restore the cluster running now from. It also compares the
cluster's system identifier against the ones the stanza describes, and stops if
none matches, which is what happens when an inventory names a repository
belonging to a different cluster.
