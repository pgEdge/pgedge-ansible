# Unreleased

These notes describe the changes since v1.1.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

This release adds recovery of an existing cluster from its pgBackRest
repository, and reworks when the collection takes a backup so that redeploying a
cluster can never discard the recovery point its repository was holding.

Its main features are:

- A recovery playbook that rebuilds an HA cluster from its pgBackRest
  repositories, optionally to a point in time: the Ultra-HA deployment with a
  new `recover_postgres` role in place of `setup_postgres`, preceded by a new
  `wipe_cluster` role and followed, once the result is right, by a commit. See
  [Recovering a Cluster from Backup](../recovery.md).
- A new `finalize_backrest` role that creates the stanza, the first backup and
  the backup schedule at the end of a deployment, and takes that first backup
  only when the repository holds none.
- An etcd certificate authority that can be supplied from Ansible Vault, so a
  controller other than the one that first deployed the cluster can manage it.
- `backup_repo_cipher` no longer has a default, because the default could be
  derived by anyone who knew the cluster's name.

## Upgrading from v1.1.0

A playbook written for v1.1.0 needs changes to work with this release. Read this
section before running the new collection against an existing cluster, or
before deploying with a playbook you wrote for v1.1.0. The sample playbooks
under `sample-playbooks/` already include every change below.

### Reorder the backup roles

`setup_backrest` now writes configuration files only, and the steps that need a
running cluster moved to the new `finalize_backrest` role. A playbook that still
ends with `setup_backrest` and never applies `finalize_backrest` **runs without
an error and sets up no backups**. Nothing creates the stanza, takes the first
backup, or installs the cron entries, and a non-HA cluster never gets its
`archive_command`.

!!! danger "An HA cluster fills its disk"
    On an HA cluster the result is worse than having no backups. Patroni now
    renders the pgBackRest `archive_command` into the Postgres configuration
    itself, so Postgres starts archiving as soon as Patroni starts it. Without a
    stanza every archive attempt fails, Postgres keeps every WAL segment until
    one succeeds, and `pg_wal` grows until the disk is full.

!!! note "Archive failures before the stanza exists are expected"
    Even with the roles in the right order, the Postgres log on an HA cluster
    shows failed `archive-push` attempts from the moment Patroni starts Postgres
    until `finalize_backrest` creates the stanza at the end of the deployment.
    This is expected. Postgres keeps the WAL it could not archive, and the
    archiver sends all of it to the repository once the stanza exists. If the
    failures continue after `finalize_backrest` has run, look into them: they
    are no longer part of the deployment.

Make the following changes to every playbook that configures backups:

1. In the play for the `pgedge` hosts, move `setup_backrest` so it comes before
   `setup_postgres`. On an HA cluster that also puts it before `setup_patroni`.
2. Keep `setup_backrest` in the play for the `backup` hosts.
3. Add a final play that applies `finalize_backrest` to both groups, after
   `setup_pgedge` and after the backup servers are configured.

The roles in an Ultra-HA playbook then run in the following order. The
`collections` keys and the `when` conditions on the etcd and pgBouncer roles are
left out here; `sample-playbooks/ultra-ha/playbook.yaml` has them.

```yaml
- hosts: all
  roles:
  - init_server

- hosts: pgedge
  roles:
  - install_repos
  - install_pgedge
  - install_etcd
  - install_patroni
  - install_backrest
  - setup_backrest      # moved: before setup_postgres
  - setup_postgres
  - setup_etcd
  - setup_patroni

- hosts: haproxy
  roles:
  - setup_haproxy

- hosts: pgedge
  roles:
  - setup_pgedge

- hosts: backup
  roles:
  - install_repos
  - install_backrest
  - setup_backrest

- hosts: pgedge:backup  # new: the last play in the playbook
  roles:
  - finalize_backrest
```

Running `finalize_backrest` against an existing cluster is safe. It takes a full
backup only when the stanza holds none, so a repository that already has
backups keeps them. It also checks the archive command in Patroni's
configuration store, and changes it only when the store does not already
point at pgBackRest.

### Set backup_repo_cipher

`backup_repo_cipher` no longer has a default. When a repository is configured
and `backup_repo_cipher_type` is `aes-256-cbc`, which is the default,
`init_server` stops the playbook until the parameter is set. This applies to
existing clusters as well. They keep running, but the next playbook run
against one stops in `init_server`.

The repository of an existing cluster is encrypted with the old derived
password. You can recover that password, because anyone could derive it.
[Upgrading a cluster deployed before this was required](../configuration/backup.md#upgrading-a-cluster-deployed-before-this-was-required)
gives the command. Store the value in Ansible Vault and set
`backup_repo_cipher` from it.

The derived password included the zone, so every zone of a cluster that used
the default has a different password. The sample inventories and the role
documentation set one `backup_repo_cipher` for the whole cluster. That is fine
for a new cluster, because nothing requires the zones to differ. It is wrong for
an upgraded multi-zone cluster. A single value matches at most one zone's
repository. The playbook rewrites `pgbackrest.conf` on every other zone with the
wrong password. `setup_backrest` now notices when the new file cannot read a
stanza that the current file can, and stops before writing it, so archiving on
those zones' primaries keeps working, but the playbook cannot go further until
each zone has its own password.

Recover the password of each zone, store each one in Ansible Vault, and select
it by zone. Keep the setting under `all` so that the backup servers resolve the
same value as the nodes they serve:

```yaml
# vault.yaml
vault_backup_repo_ciphers:
  1: <recovered password for zone 1>
  2: <recovered password for zone 2>
```

```yaml
all:
  vars:
    backup_repo_cipher: "{{ vault_backup_repo_ciphers[zone | int] }}"
```

A cluster that already set `backup_repo_cipher` explicitly does not need this
step, because its repositories already use the value in its inventory.

Treat a recovered password as compromised. It lets you keep reading the
existing repository, but you should plan to re-encrypt the repository.

A new cluster needs a password of your own choosing. If the storage layer
encrypts the repository, for example with S3 default bucket encryption, you
can set `backup_repo_cipher_type: none` instead.

### Supply the etcd certificate authority to other controllers

Every play that signs etcd or Patroni certificates now reads the certificate
authority that the running etcd members trust, and stops unless the controller
holds the same one. A cluster deployed from one controller and managed from
another, such as a second workstation or a CI runner, needs `etcd_ca_cert` and
`etcd_ca_key` set from Ansible Vault before that controller can run the
playbook. Previously a controller without the authority generated a new one and
reissued the cluster's certificates against it, and Patroni then could not
reach etcd. The play also stops when the controller's `tls/etcd/` holds the
certificate without its private key, or with a key that does not match it,
which previously generated a new authority over the staged one.
[etcd_ca_cert and etcd_ca_key](../configuration/etcd.md#etcd_ca_cert-and-etcd_ca_key)
describes how to capture the authority from the original controller.

A cluster that is only ever managed from the controller that deployed it needs
no change.

Any cluster whose Patroni uses etcd can still meet one new stop. The check asks
every host in the `pgedge` group, not only the hosts the play runs on, so
`setup_patroni`, and `setup_etcd` whenever it builds a node, now stop when any
pgEdge host in the inventory is unreachable, naming that host, even under
`--limit`. Previously an unreachable host dropped out of the play and the rest
carried on. Bring the host back, or remove it from the inventory if it has left
the cluster for good.

### Gather facts for every host first

Roles read other hosts' addresses from the facts gathered for those hosts, so
the first play in a playbook must target every host in the inventory, without
`become`. Gathering facts without `become` also records the login account
rather than `root`. The Ultra-HA sample already applies `init_server` to `all`
in its first play. The simple-cluster sample now starts with a play that only
pings every host. If your playbook's first play targets a single group, add the
same play to the top:

```yaml
- hosts: all
  any_errors_fatal: true

  tasks:
  - name: Confirm every host in the inventory is reachable
    ping:
```

## Changes

### Added

- New `wipe_cluster` role and `sample-playbooks/wipe-cluster/` playbook tear a
  cluster down for a redeployment or a recovery. They stop Postgres, Patroni,
  pgBouncer and the collection's etcd, remove the cluster from any other
  configuration store with `patronictl`, remove the backup schedule, and erase
  the components' configuration and data. No repository is touched, and the
  wipe is refused unless `wipe_confirm` is set and some zone's repository holds
  a backup of the cluster in it.
- New `recover_postgres` role builds the cluster's Postgres from a backup, in
  place of `setup_postgres`. It applies `setup_postgres` to every node, restores
  `recovery_node` from its zone's repository and promotes it outside Patroni,
  strips the restored node's stale Spock metadata, and upgrades each zone's
  stanza to describe the cluster now in it. One zone is restored and every other
  zone copies it across Spock, because each zone's stanza restores to its own
  moment, and zones restored separately have no common position to replicate
  forward from.
- New `sample-playbooks/ultra-ha-recover/` holds the recovery playbook, which is
  the Ultra-HA deployment playbook with `recover_postgres` in place of
  `setup_postgres`, and `commit-restore.yaml`, which applies
  `finalize_backrest` once the recovered cluster is the one to keep. The
  recovery takes no backups and leaves the schedule off, so it can be repeated
  to another target or from another zone with every backup still in place.
- New `recovery_node`, `recovery_target_type`, `recovery_target`,
  `recovery_target_timeline` and `recovery_backup_set` parameters drive a
  recovery. Only `recover_postgres` reads them.
- New `pgedge_seed_zone` parameter for `setup_pgedge` names a zone that already
  holds the cluster's data. Every other zone copies it with
  `synchronize_structure` and `synchronize_data` before the rest of the mesh is
  built. The recovery playbook sets it to the restored zone.
- New `pgedge_seed_stall_minutes` parameter (default 15) for `setup_pgedge`
  bounds the wait for that copy by progress, not time. The wait polls
  `spock.sub_show_status()` and the sync status instead of calling
  `spock.sub_wait_for_sync()`, which keeps waiting while Spock retries a failed
  copy. It fails at once on a disabled subscription, after two minutes of an
  apply worker that will not stay up (a bad DSN or password, or a copy that
  broke partway), or after the stall window without progress. It reports the
  subscription status and the Spock lines from the Postgres log.
  `pgedge_seed_max_hours` (default 24) remains the backstop.
- New `patroni_replica_from_backup` parameter makes Patroni rebuild a replica
  with a pgBackRest delta restore instead of a fresh `pg_basebackup` from its
  zone's leader, falling back to `pg_basebackup` (`pg_clonecluster` on Debian)
  if the restore fails. Off by default. The restore runs through
  `/usr/local/bin/patroni_pgbackrest_replica`, which first asks the leader for
  its system identifier and timeline history and fails, without restoring,
  unless the newest backup is of the leader's cluster and ends on its history.
  After a point-in-time recovery that stopped before the newest backup, the
  replicas therefore fall back instead of restoring a backup they cannot
  follow.
- New `finalize_backrest` role initializes the backup repository and the backup
  schedule: the backup database user, the stanza, the first backup and the cron
  entries. It is applied at the end of a deployment, where a running cluster
  exists for it to act on. The backup user, and in S3 mode the stanza and the
  first backup, come from each zone's current Patroni leader, so the role works
  on an HA cluster that has failed over away from its first node.
- `role_config` gained a `repo_identity` task file that compares a node's
  cluster against the one its stanza describes, and refuses when they disagree.
  `setup_postgres` asks it before initializing a data directory and
  `finalize_backrest` asks it before writing to the repository. The early check
  turns the disaster-recovery case — replacement hardware, the original
  inventory, and a repository that outlived the cluster — into a stop with an
  explanation rather than an empty cluster that can never archive to its own
  repository. It skips a repository it cannot reach, since an SSH repository is
  not reachable from a pgEdge node that early; the late check, which gates a
  decision to write, treats an unreadable repository as fatal.
- `recover_postgres` runs `pgbackrest stanza-upgrade` on every zone whose
  stanza does not describe the cluster now in it. A rebuilt zone comes back with
  a system identifier its stanza has never seen, so PgBackRest would refuse to
  archive there, and `pg_wal` would keep every segment through the Spock copy.
  The upgrade only adds an entry to the stanza's history: every earlier backup
  stays in place and restorable, which is what lets a recovery be retried from
  that zone before it is committed.
- `finalize_backrest` takes a full backup when the stanza's newest backup of
  the cluster cannot restore it: after a point-in-time recovery the newest
  backups can lie on the timeline the recovery abandoned, past the point the
  cluster branched away. It reads the cluster's timeline history from the
  zone's primary (from its first pgEdge node when a backup server asks). A
  failover branches after every backup, so it never causes one.
- `finalize_backrest` counts only backups of the cluster running now, matched by
  system identifier, so a stanza that holds only backups of a cluster a recovery
  replaced is treated as having none.
- The Ultra-HA end-to-end test now verifies the backup surface rather than
  printing it. It asserts that the running server's `archive_command` invokes
  pgBackRest rather than the template's `/bin/true` placeholder, that WAL
  archiving is currently succeeding according to `pg_stat_archiver`, and that
  the repository holds exactly one healthy stanza with exactly one full backup.
  It then re-applies `finalize_backrest` and asserts the repository holds the
  same backups afterwards, which is the assertion that would have caught the
  destructive behaviour this release removes: a second full backup expires its
  predecessor under the default retention, so a repository rewritten that way
  still holds one backup and only its label changes.
- The recovery waits for the restored node's replay by watching whether it is
  still making progress rather than by counting attempts. How long a replay
  takes is a property of the database, so any fixed budget is wrong for some
  cluster. The wait follows the node's log and `pg_control`'s timestamp, and
  gives up only when neither has moved for `recovery_stall_minutes` (default
  15), or at once if Postgres stops. `recovery_max_hours` (default 24) is a hard
  ceiling. The restore and the wait run under `async`, so neither is lost with
  an SSH connection.
- New `etcd_ca_cert` and `etcd_ca_key` supply the certificate authority that
  signs etcd's certificates and every node's Patroni client certificate from
  Ansible Vault. Previously the authority existed only on the controller that
  first deployed the cluster, so any other controller — including a fresh CI
  runner — could not add a replica, rebuild a node, recover the cluster, or
  re-run the deployment. The etcd configuration page now explains how to
  generate a new authority or capture an existing one, and how to vault it.
  Both parameters are empty by default and an inventory that sets neither
  behaves exactly as before. A supplied authority that differs from the one
  already staged is refused rather than applied, because signing against a
  different authority than the running etcd trusts leaves no node able to reach
  the store.
- Adding or rebuilding a node from a controller without the cluster's
  certificate authority no longer generates a new one. The etcd setup skipped
  nodes that already ran etcd but not the node being added, so it minted an
  authority for that node, and every node's Patroni client certificate was then
  reissued against an authority the running etcd did not trust. Every play that
  signs certificates now reads the authority each existing etcd member trusts
  and stops unless the controller holds that one.
- New `tests/render/check-patroni.py` renders the Patroni template offline
  across every combination of the backup switches, and asserts that a template
  rendered without facts for the proxy and backup hosts fails rather than
  emitting HBA rules with no addresses in them. Run by both workflows and both
  local harnesses.
- New `tests/run-recovery-test.sh`, `tests/playbooks/seed-recovery.yml`,
  `tests/verify/verify-recovery.yml` and `tests/verify/verify-commit.yml`
  exercise a recovery against a cluster the end-to-end harness has already
  deployed: wipe, recover, verify, commit, verify. The seed writes rows *after*
  the deployment's backup, so they exist only in archived WAL: a recovery has
  to replay the archive to return them to the restored zone and carry them
  across Spock to the zones rebuilt empty. The seed also records each zone's
  system identifier and timeline on the controller, and the verification
  asserts the restored zone kept its identifier and moved to a later timeline
  while every rebuilt zone has a new one. A second pass, `lsn`, seeds a further
  batch after a recorded WAL position, recovers to that position and asserts
  the batch stayed out; the Ultra-HA workflow's `recover_to` input picks
  `latest`, `lsn` or `both`. Every zone-wide check runs against the leader
  Patroni names, and fails a zone with no leader rather than skipping it. The
  verification also asserts the replication mesh was rebuilt to exactly the
  expected size, that every replica came back, that writes made afterwards
  reach every zone, that each zone can archive again, and that the recovery
  took no backup. After the commit it
  asserts every zone has a backup of the cluster it runs.
- New `backup_stanza` and `backup_repo_configured` variables in `role_config`,
  so that the roles which now share them cannot drift apart.
- New `uri_style`, `storage_ca_file`, `storage_port` and `storage_verify_tls`
  keys in `backup_repo_params` set PgBackRest's `repo1-s3-uri-style`,
  `repo1-storage-ca-file`, `repo1-storage-port` and `repo1-storage-verify-tls`,
  which an S3-compatible store such as MinIO usually needs: path-style
  addressing, a port of its own, and a certificate authority for an endpoint
  whose certificate is privately signed -- or, in a test environment, no
  certificate check at all. All four are empty by default and omitted from the
  configuration when empty, so an AWS S3 repository renders exactly as before.
  `backup_repo_params` and the merged `backup_params` moved from
  `setup_backrest` to `role_config`, because `init_server` now validates them.
- `init_server` refuses an S3 repository whose `backup_repo_params` leaves the
  credentials, bucket, region or endpoint empty, or gives a `uri_style` other
  than `host` or `path`, a `storage_port` outside 1 to 65535, or a
  `storage_verify_tls` that is not a boolean. Empty credentials used to surface
  only when `finalize_backrest` first wrote to the repository, at the very end
  of the deployment.
- `init_server` refuses a zone that uses an S3 repository and also has a host in
  the `backup` group. A backup server only serves an SSH repository, and in S3
  mode no SSH keys are exchanged, so the server failed partway through the
  deployment trying to reach nodes it was never given access to.

### Changed

- `setup_backrest` no longer replaces a `pgbackrest.conf` that can read the
  stanza with one that cannot. A wrong `backup_repo_cipher` or object-store key
  used to be written straight over a working file, which broke archiving on the
  live primaries at once while the run carried on through `setup_patroni` and
  `setup_pgedge`. The new file is now rendered beside the old one and both are
  asked to read the stanza first. The previous file is also kept as a backup
  each time it changes, with the same owner and mode.
- The initial backup is now taken only when the repository reports that the
  stanza holds none, rather than on every run. `full_backup_count` defaults to
  `1`, so a full backup taken against a repository that already had one expired
  the previous full backup and its WAL the moment it completed — discarding the
  recovery point a redeployed cluster was about to be restored from. The
  decision is now made from the repository's contents rather than from where the
  role sits in a playbook.
- `setup_backrest` now writes files only and touches Postgres not at all, and
  moves before `setup_postgres` in the role order. An HA cluster gets its
  `archive_command` from the Patroni configuration, so Postgres starts archiving
  the moment Patroni starts it, and a `pgbackrest.conf` written later left a
  window in which every archive attempt failed. Placing it before
  `setup_postgres` also lets that role ask the repository whether it already
  holds a cluster before initializing a data directory. A non-HA cluster's
  `archive_command` and `restore_command` moved to `finalize_backrest`, which runs
  when Postgres is up to be reloaded.
- The recovery refuses, before building anything, a rebuilt zone whose SSH
  repository is named only by `backup_host`. `stanza-upgrade` has to run on the
  repository host, and a host outside the inventory would never be upgraded, so
  the zone could not archive. Adding the server to the `backup` group lets the
  recovery upgrade it.
- `setup_postgres` on Debian now removes the configuration files of a cluster
  whose configuration directory outlived its data directory before creating it
  again, since `pg_createcluster` refused to recreate a cluster whose
  configuration was still in `/etc/postgresql`. This includes a cluster named
  `main`, which was previously never created by the role and so was left
  without a cluster once its data directory was erased. It also lets
  `cluster_name: main` with a `pg_data` of its own replace the package's `main`
  cluster on a fresh install: the role stops that cluster and replaces its
  configuration, and leaves its data directory where it is.
- `archive_command` and `restore_command` for an HA cluster now come from
  `setup_patroni`'s configuration template rather than being patched into the
  Patroni configuration store by `setup_backrest`. A value held only in the
  store is lost when the store is rebuilt, which is what a recovery does: a
  recovered cluster came back with `archive_command` reverted to `/bin/true`
  and silently stopped archiving.
  The patch in `setup_backrest`'s `config_postgres_ha.yaml` has been replaced
  by a check in `finalize_backrest`. Patroni applies the template only when it
  bootstraps a cluster, so an HA cluster deployed without a backup server and
  given one later still has `/bin/true` in its configuration store.
  `finalize_backrest` now reads the store, patches it only when it disagrees,
  and waits for Postgres to take up the new command before the first backup.
- The Patroni template now spells replica creation as `create_replica_methods`
  rather than the legacy `create_replica_method`. Patroni reads both, although
  its configuration validator knows only the new spelling. Debian replicas are
  still built with `pg_clonecluster` by default, as before. Debian needs it: it
  creates the `/etc/postgresql` configuration directory that `basebackup`
  leaves out. With `patroni_replica_from_backup` enabled, a Debian replica
  tries the pgBackRest restore first, through a script `setup_patroni`
  installs at `/usr/local/bin/patroni_pgbackrest_replica`, which creates that
  directory after the restore; `pg_clonecluster` is the fallback.

### Security

- `backup_repo_cipher` no longer defaults to a value derived from `cluster_name`
  and `zone`. Both are public, so the password protecting every backup was
  reproducible by anyone who knew the cluster's name — encryption in form only.
  It cannot be defaulted at all: a generated password must be identical on every
  run, or the repository stops being readable, and must also be unguessable, and
  nothing can be both. `init_server` now requires one, the way it already
  requires the other passwords, and the parameter moved to `role_config` so that
  validation and the configuration template read the same value.

  Existing clusters keep running, but the next playbook run against one stops
  in `init_server` until the parameter is set. Their repositories are encrypted
  with the old derived password, and the derivation was public, so it can be
  recovered — [Backup Configuration](../configuration/backup.md#upgrading-a-cluster-deployed-before-this-was-required)
  gives the command. Treat a recovered value as compromised and plan to
  re-encrypt.
- A collection tarball built with `make build` no longer includes private keys
  left in the tree by local runs. `ansible-galaxy` ignores `.gitignore`, so the
  etcd CA and node keys the sample playbooks write under `tls/`, the SSH host
  keys under `host-keys/`, and the test harness's SSH key were all packaged.
  `galaxy.yml` now excludes them, along with all of `tests/` and other local
  files. Anyone who built and shared a tarball from a tree where these existed
  should treat the keys in it as exposed.

### Fixed

- `backup_repo_cipher_type: none` now produces a configuration PgBackRest
  accepts. The repository template emitted `repo1-cipher-pass` unconditionally,
  and PgBackRest rejects a password alongside a cipher type of `none`, so
  leaving encryption to the storage layer was not expressible — which is the
  arrangement that permits key rotation, since PgBackRest cannot rotate its own
  cipher. The password line is now emitted only where something is encrypting,
  and `init_server` rejects a password set where nothing is.
- `wipe_cluster` does not treat an external configuration store it cannot read
  as a store with no cluster in it. An unreadable store stops the wipe before
  anything is erased, rather than leaving Patroni waiting forever for a leader
  whose key is still there.
- `wipe_cluster` removes a zone's cluster from an external configuration store
  even when the store lists no members, and then checks that `patronictl`
  reports the cluster as `uninitialized`. Members expire within Patroni's `ttl`
  of Patroni stopping, but the keys recording the cluster as initialized do
  not, so a wipe run after Patroni had been down for longer skipped the removal
  and passed its own check. The rebuilt zones then met the old system
  identifier and Patroni refused to start them. A node with no Patroni
  configuration, such as a freshly provisioned host, now reaches the store with
  a temporary configuration built from the inventory's `patroni_dcs` settings,
  instead of being skipped.
- `backup_repo_user` and `backup_repo_path` no longer derive from
  `ansible_user_id`. That is a fact, and a fact records which account the setup
  module ran as, so a play that gathers facts with `become` records `root` --
  and because fact gathering is smart by default, one such play poisons the
  value for every later play in the same run. The repository owner became
  `root` and its path `/home/root`. PgBackRest refuses to run as root, which is
  the only reason this surfaced at all rather than quietly building a
  repository somewhere nobody would look for it. Both now derive from a new
  `connection_user` in `role_config`, which prefers the `ansible_user`
  connection variable and falls back to the fact only where no login user is
  configured. `init_server` compares against the same value.
- `setup_backrest` no longer skips its client configuration entirely when
  `backup_repo_type` is `s3`. The role gated client setup on a backup server
  being named, and an S3 repository names none, so S3 clusters were left with no
  `pgbackrest.conf`, no archive command and no backups, with nothing reporting
  it. The gate is now whether a repository is configured at all.
- `setup_patroni` finds the primary when Postgres listens on a port other than
  5432. `patronictl` then shows each member's host as `host:port`, and the wait
  for the primary compared that with the bare inventory name, so it never saw
  the primary come up and failed after its retries. The port is now stripped
  before the comparison.
- `make build` rebuilds the tarball when a file is deleted from the
  collection, and when a doc page or sample playbook changes. It compared only
  the role and meta files that still existed, so a deletion left a stale
  tarball in place — under the same name, since a dirty tree keeps its version
  string — and `make install` reinstalled the removed file.
