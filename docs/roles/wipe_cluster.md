# wipe_cluster

The `wipe_cluster` role tears down a pgEdge cluster so that it can be deployed
or recovered again. It stops every component this collection runs on the
cluster's hosts and erases their configuration and data, and it never touches
a backup repository.

The role performs the following tasks on inventory hosts:

- Refuse to start unless `wipe_confirm` is `true`.
- Refuse to wipe a cluster when no zone's repository holds a backup of the
  cluster in that zone, unless `wipe_without_backup` is `true`.
- Remove the scheduled backups from the pgEdge nodes and the backup servers.
- Stop and disable Patroni, Postgres and pgBouncer, and stop any postmaster
  that is still running on the data directory.
- Stop etcd and erase its data when the collection hosts it; otherwise remove
  each zone's cluster from the configuration store with `patronictl remove`.
- Erase the Postgres data directory's contents, the Debian cluster
  configuration, the Patroni configuration and certificates, the pgBouncer
  configuration, and the etcd configuration and certificates.

The role leaves the following alone:

- Backup repositories, stanzas, archives and `pgbackrest.conf`.
- Packages, package repositories and the unit files the install roles write.
- HAProxy, which holds no state and is rewritten by `setup_haproxy`.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

Apply this role to the pgEdge nodes and the backup servers before deploying a
cluster again on the same hosts, or before
[recovering it from its repository](../recovery.md):

```yaml
- hosts: pgedge:backup
  collections:
    - pgedge.platform
  roles:
    - wipe_cluster
```

The `sample-playbooks/wipe-cluster` playbook does exactly this. Pass the
confirmation on the command line rather than writing it into an inventory:

```bash
ansible-playbook playbook.yaml -i inventory.yaml -e wipe_confirm=true
```

## Configuration

This role uses the following parameters:

| Parameter | Use Case |
|-----------|----------|
| `wipe_confirm` | Must be `true` for the role to do anything (default: `false`). |
| `wipe_without_backup` | Wipe the cluster even when no zone's repository holds a backup of it (default: `false`). Also needed to retry a recovery that failed before its restore finished; see [Trying Again](../recovery.md#trying-again). |
| `patroni_dcs` | Decides whether the store is the collection's etcd or an external one. |

## How It Works

The role does not unwind the cluster in order, because nothing in it has to
survive. Each step looks for its component first and acts only on what it
finds, so the role runs cleanly against hosts that never had a component, such
as a deployment that failed partway or freshly provisioned replacements. Each
step finishes on every host before the next begins: every Patroni is stopped
before the store is cleared, and the store is cleared before anything is
erased.

### The Backup Check

Once the cluster is wiped, its data survives only in the backup repositories.
Every zone holds the same data, replicated across Spock, so a backup in any
one zone is enough. The role asks each zone's repository whether it holds a
backup of the cluster in that zone, matched by system identifier, and refuses
only when none does. That is also what lets a recovery be retried: until it is
committed, the zones it rebuilt have no backups of their own, but the zone it
restored still has the backups it came from.

### The Configuration Store

Patroni records in its store that each zone's cluster has been initialized,
and a node with an empty data directory whose cluster is still recorded waits
for a leader instead of bootstrapping. The store therefore has to forget the
cluster as well.

When `patroni_dcs` is an `etcd` or `etcd3` store without `parameters`, the
store is the etcd the collection hosts on the pgEdge nodes. It holds nothing
but this cluster, so the role stops etcd and erases its data, and `setup_etcd`
builds it again from nothing. Any other store is shared with whatever else
uses it, so the role only removes each zone's cluster from it with
`patronictl remove`, once per zone from the zone's first node.

The role removes the cluster whenever it can read the store, whether or not the
store lists any members. Members are held on a lease that expires shortly
after Patroni stops, but the keys that record the cluster as initialized are
not, and a rebuilt zone that meets them is refused by Patroni. Afterwards the
role checks that `patronictl list` reports the cluster as `uninitialized`, and
stops if it does not or if the store cannot be read.

`patronictl` finds the store through Patroni's configuration file. On a node
that has none, such as a freshly provisioned host or one where a deployment
failed early, the role writes a temporary configuration holding
`patroni_scope`, `patroni_namespace` and `patroni_dcs` from the inventory, and
removes it afterwards. Any file those settings name, such as a TLS
certificate, must already exist on the node. `patronictl` itself must be
installed: the role stops before erasing anything on a node without it, so
apply `install_patroni` to such a node before wiping it.

### Scheduled Backups

The scheduled backups are removed before anything is stopped. A full backup
taken against a recovered cluster before the operator commits to the result
would expire the backup the recovery restored from. `finalize_backrest`
installs the schedule again when it runs.

## Idempotency

This role is safe to re-run. A second run finds nothing running and nothing to
erase, and the backup check passes because a wiped cluster has nothing to
lose.
