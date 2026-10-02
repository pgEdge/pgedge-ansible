# Unreleased

These notes describe the changes since v1.1.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

This release adds recovery of an existing cluster from its pgBackRest
repository, and reworks when the collection takes a backup so that redeploying a
cluster can never discard the recovery point its repository was holding.

Its main features are:

- A `recover_cluster` role and recovery playbook that rebuild an HA cluster
  from its pgBackRest repository, optionally to a point in time. See
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
wrong password, and archiving fails on those zones' primaries.

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

- New `recover_cluster` role and `sample-playbooks/recover-cluster/` playbook
  rebuild an existing HA cluster from a pgBackRest repository, optionally to a
  point in time. One zone is restored from its repository and every other zone
  is rebuilt empty and refilled across Spock from the restored one, because each
  zone's stanza describes an independent physical cluster restored to an
  independent moment, and zones restored separately have no common position to
  replicate forward from. See
  [Recovering a Cluster from Backup](../recovery.md).
- New `recovery_node`, `recovery_target_type`, `recovery_target`,
  `recovery_backup_set` and `recovery_confirm` parameters drive a recovery.
  All are empty or false by default, so an ordinary deployment renders exactly
  the configuration it did before.
- `setup_patroni` now renders a pgBackRest bootstrap method for the node
  `recovery_node` names, so Patroni restores that node from the repository
  rather than initializing an empty one. Patroni consults the `bootstrap`
  section only when it is genuinely bootstrapping a cluster, so the addition is
  inert on a running cluster.
- New `patroni_replica_from_backup` parameter makes Patroni rebuild a replica
  with a pgBackRest delta restore instead of a fresh `pg_basebackup` from its
  zone's leader, falling back to `pg_basebackup` if the restore fails. Off by
  default.
- New `finalize_backrest` role initializes the backup repository and the backup
  schedule: the backup database user, the stanza, the first backup and the cron
  entries. It is applied at the end of a deployment, where a running cluster
  exists for it to act on.
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
- The recovery playbook now runs `pgbackrest stanza-upgrade` on every rebuilt
  zone. Those zones come back with a system identifier their stanza has never
  seen, so PgBackRest would refuse to archive there and the zone would finish
  the recovery unable to back itself up. The upgrade records the new cluster as
  another entry in the stanza's history and leaves the earlier backups in
  place, where retention expires them as new full backups accumulate. It runs
  as soon as each zone's leader is rebuilt, before the Spock refill, so the WAL
  that copy generates is archived as it goes, not kept in `pg_wal` until the
  end of the recovery.
- The recovery playbook now takes a full backup of every rebuilt zone once it
  has been refilled, before any replica is rebuilt, and of the restored zone
  too when the recovery stopped at a point-in-time target. A rebuilt zone's
  stanza otherwise held only backups of the cluster it replaced, so a second
  incident there would restore that cluster, and a replica built with
  `patroni_replica_from_backup` would be cloned from it and never stream. After
  a point-in-time recovery the restored zone's later backups are on the
  timeline the recovery abandoned. A recovery that replays the whole archive
  leaves the restored zone's backups alone, so it can be run again with a
  different target.
- The recovery's validation and `finalize_backrest`'s first backup count only
  backups taken under the stanza's newest db entry, the cluster running now.
  A recovery refuses to start from a zone whose backups all belong to a
  replaced cluster, or when `recovery_backup_set` names one of those, and
  `finalize_backrest` treats such a stanza as having no backup.
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
- The recovery waits for the restore by watching whether it is still making
  progress rather than by counting attempts. How long a restore takes is a
  property of the database -- a full backup read out of the repository plus
  every WAL segment since -- so any fixed budget is wrong for some cluster. The
  waiter follows PgBackRest's restore log, `pg_control`'s timestamp and the size
  of the data directory, and gives up only when none has moved for
  `recovery_stall_minutes` (default 15). A restore that keeps moving is left
  alone however long it takes, and one that has wedged is reported in minutes
  rather than after a timeout drains. It runs under `async`, so a restore that
  outlasts an SSH connection is not lost with it.
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
  and stops unless the controller holds that one. A recovery makes the same
  check before it erases anything, unless `recovery_reset_dcs` is rebuilding
  the store.
- New `recovery_reset_dcs` rebuilds the distributed configuration store from
  nothing rather than removing the cluster from it, for when the store itself is
  what is broken -- etcd that has lost quorum, or keys a half-finished recovery
  left behind. It reissues each node's Patroni client certificate so the store
  and the nodes agree on a certificate authority. Applies only to the etcd
  cluster the collection deploys; an external store is reset by whoever runs it.
- New `tests/render/check-patroni.py` renders the Patroni template offline
  across every combination of the recovery switches, and asserts that a
  template rendered without facts for the proxy and backup hosts fails rather
  than emitting HBA rules with no addresses in them. The recovery playbook
  re-renders that template on the restored node partway through, after the
  cluster has been erased, so a template that cannot render there is expensive
  to discover live. Run by both workflows and both local harnesses.
- New `tests/run-recovery-test.sh`, `tests/playbooks/seed-recovery.yml` and
  `tests/verify/verify-recovery.yml` exercise a recovery against a cluster the
  end-to-end harness has already deployed. The seed writes rows *after* the
  deployment's backup, so they exist only in archived WAL: a recovery has to
  replay the archive to return them to the restored zone and carry them across
  Spock to the zones rebuilt empty. Every other check passes on an empty
  cluster, so this is what separates a restore from a rebuild. The verification
  also asserts the replication mesh was rebuilt to exactly the expected size --
  too many node entries or origins means metadata from before the recovery
  survived -- that every replica came back, and that each zone can archive
  again, which is what proves `stanza-upgrade` took on the rebuilt zones.
- New `backup_stanza` and `backup_repo_configured` variables in `role_config`,
  and `subscribe_target` moved there from `setup_pgedge`, so that the roles
  which now share them cannot drift apart.

### Changed

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
- The recovery playbook refuses, before erasing anything, a rebuilt zone whose
  SSH repository is named only by `backup_host`. `stanza-upgrade` has to run on
  the repository host, and a host outside the inventory would never be
  upgraded, so the zone could not archive and would fail `finalize_backrest`'s
  identity check at the end. Adding the server to the `backup` group lets the
  recovery upgrade it.
- `setup_postgres` on Debian now drops a cluster whose configuration directory
  outlived its data directory before creating it again. A recovery erases the
  data directory of every zone it rebuilds, and `pg_createcluster` refused to
  recreate a cluster whose configuration was still in `/etc/postgresql`. This
  includes a cluster named `main`, which was previously never created by the
  role and so was left without a cluster once a recovery erased it.
- `recover_cluster`'s quiesce step now acts only on systemd units that exist, so
  a recovery can be run against replacement hardware where the deployment
  stopped before creating them. On RHEL the Postgres unit file is written by
  `setup_postgres`, and asking systemd to stop a unit it does not have is an
  error rather than a no-op.
- `archive_command` and `restore_command` for an HA cluster now come from
  `setup_patroni`'s configuration template rather than being patched into the
  Patroni configuration store by `setup_backrest`. A value held only in the
  store is lost when the cluster is removed from the store and bootstrapped
  again, which is what a recovery does: a recovered cluster came back with
  `archive_command` reverted to `/bin/true` and silently stopped archiving.
  The patch in `setup_backrest`'s `config_postgres_ha.yaml` has been replaced
  by a check in `finalize_backrest`. Patroni applies the template only when it
  bootstraps a cluster, so an HA cluster deployed without a backup server and
  given one later still has `/bin/true` in its configuration store.
  `finalize_backrest` now reads the store, patches it only when it disagrees,
  and waits for Postgres to take up the new command before the first backup.
- The Patroni template now spells replica creation as `create_replica_methods`
  rather than the legacy `create_replica_method`. Patroni reads both, although
  its configuration validator knows only the new spelling. Debian replicas are
  still built with `pg_clonecluster`, as before. Debian needs it: it creates
  the `/etc/postgresql` configuration directory that `basebackup` leaves out.

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

### Fixed

- `backup_repo_cipher_type: none` now produces a configuration PgBackRest
  accepts. The repository template emitted `repo1-cipher-pass` unconditionally,
  and PgBackRest rejects a password alongside a cipher type of `none`, so
  leaving encryption to the storage layer was not expressible — which is the
  arrangement that permits key rotation, since PgBackRest cannot rotate its own
  cipher. The password line is now emitted only where something is encrypting,
  and `init_server` rejects a password set where nothing is.
- `recover_cluster` no longer treats a configuration store it cannot read as a
  store with no cluster in it. The check that runs before any data directory is
  erased folded a failed `patronictl` into an empty member list, so an etcd that
  had stopped answering would pass it -- and the recovery would erase the whole
  cluster and then leave Patroni waiting forever for a leader whose key was
  still sitting there. An unreadable store now stops the recovery with nothing
  erased, and names `recovery_reset_dcs` as the way past it.
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

