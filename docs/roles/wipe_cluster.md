# wipe_cluster

The `wipe_cluster` role tears down a pgEdge cluster so that it can be deployed
or recovered again. It stops every component this collection runs on the
cluster's hosts and erases their configuration and data, and it never touches
a backup repository.

The role performs the following tasks on inventory hosts:

- Refuse to start unless `wipe_confirm` is `true`.
- Refuse to wipe a zone whose cluster exists but whose repository holds no
  backup of it, unless `wipe_without_backup` is `true`.
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
| `wipe_without_backup` | Wipe zones whose repository holds no backup of their cluster (default: `false`). |
| `patroni_dcs` | Decides whether the store is the collection's etcd or an external one. |

## How It Works

The role does not unwind the cluster in order, because nothing in it has to
survive. Each step looks for its component first and acts only on what it
finds, so the role runs cleanly against hosts that never had a component, such
as a deployment that failed partway or freshly provisioned replacements. Each
step finishes on every host before the next begins: every Patroni is stopped
before the store is cleared, and the store is cleared before anything is
erased.

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
`patronictl remove`, and stops if the store cannot be read or still lists the
cluster afterwards.

### Scheduled Backups

The scheduled backups are removed before anything is stopped. A full backup
taken against a recovered cluster before the operator commits to the result
would expire the backup the recovery restored from. `finalize_backrest`
installs the schedule again when it runs.

## Idempotency

This role is safe to re-run. A second run finds nothing running and nothing to
erase, and the backup check passes because a wiped zone has no cluster to
lose.
