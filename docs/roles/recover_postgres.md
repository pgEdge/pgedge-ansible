# recover_postgres

The `recover_postgres` role builds a cluster's Postgres from a PgBackRest
backup instead of from nothing. It takes the place of `setup_postgres` in a
playbook, and the roles after it (`setup_etcd`, `setup_patroni`,
`setup_pgedge`) treat what it leaves exactly as they treat a new cluster. See
[Recovering a Cluster from Backup](../recovery.md) for the whole procedure.

The role performs the following tasks on inventory hosts:

- Check the recovery settings, that every pgEdge node is empty, and that the
  restored zone's repository holds a backup to restore.
- Apply `setup_postgres` to every node, as a deployment would.
- Replace the cluster on `recovery_node` with a restore from its zone's
  repository, replay WAL to the target outside Patroni, and promote it.
- Remove the Spock subscriptions, node entries and replication origins the
  restored node came back with, keeping only its own Spock node.
- Upgrade each zone's stanza to describe the cluster now in it, or create the
  stanza if it does not exist.

The role never takes a backup. Every backup the repositories hold remains
usable until [`finalize_backrest`](finalize_backrest.md) commits to the
recovery, so the recovery can be tried again to another target or from another
zone.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_postgres` builds each node before the restore replaces one of them.
- `setup_backrest` must already have written `pgbackrest.conf` on the pgEdge
  nodes and the backup servers.

## When to Use

Apply this role where a deployment applies `setup_postgres`, on hosts that
hold no cluster: freshly provisioned hosts, or hosts that
[`wipe_cluster`](wipe_cluster.md) has torn down. Set `pgedge_seed_zone` for
`setup_pgedge` to the restored zone, so the other zones copy it:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pgedge_seed_zone: "{{ hostvars[recovery_node].zone }}"
  roles:
    - setup_backrest
    - recover_postgres
    - setup_etcd
    - setup_patroni
```

## Configuration

This role uses the following parameters:

| Parameter | Use Case |
|-----------|----------|
| `recovery_node` | The first node of the zone to restore; required. |
| `recovery_target_type` | PgBackRest `--type`: `time`, `xid`, `lsn`, `name` or `immediate`; empty restores to the end of the archive. |
| `recovery_target` | The value the target type stops at. |
| `recovery_target_timeline` | PgBackRest `--target-timeline`; empty follows the newest timeline. |
| `recovery_backup_set` | A specific backup to restore, as `pgbackrest info` labels it. |
| `recovery_stall_minutes` | How long the restored node may make no progress before the role gives up (default: 15). |
| `recovery_poll_seconds` | How often the role checks the restored node (default: 30). |
| `recovery_max_hours` | A backstop on the restore and the replay (default: 24). |

## How It Works

### The Restored Node

The role restores `recovery_node` into the data directory `setup_postgres`
built, then starts Postgres directly rather than through Patroni, archiving to
the repository regardless of its configuration, so the WAL and timeline history
written at promotion reach the repository. The role waits for the end of
recovery for as long as Postgres keeps making progress, and gives up only when
nothing has moved for `recovery_stall_minutes`.

When neither `recovery_backup_set` nor a target picks a backup, the role names
the newest backup explicitly. PgBackRest's own choice is the newest backup of
the cluster the stanza describes now, and it refuses when the newest backup
belongs to an earlier one, which is the case when a zone an earlier recovery
rebuilt is restored before that recovery was committed.

After promotion the role removes the recovery settings PgBackRest wrote into
`postgresql.auto.conf`, because replicas copy that file and would otherwise
stop replaying at the same target. The node is left running, and
`setup_patroni` takes it over.

### The Other Zones

Every other zone keeps the empty cluster `setup_postgres` built, and
`setup_pgedge` fills it from the restored zone. Each zone's stanza still
describes the cluster it held before, so the role upgrades it with
`stanza-upgrade` before Patroni starts; otherwise every archive attempt is
refused and `pg_wal` grows throughout the copy. An upgrade only adds to the
stanza's history and removes no backup. With an SSH repository the upgrade
runs on the zone's backup server.

### Retrying a Recovery

A retry starts with `wipe_cluster`, then runs the recovery again with a new
target or a different `recovery_node`. A second point-in-time recovery to a
later moment than the first must set `recovery_target_timeline` to the
timeline the first one started from; otherwise it follows the timeline the
first one created.
