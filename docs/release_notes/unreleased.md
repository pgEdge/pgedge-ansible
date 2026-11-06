# Unreleased

These notes describe the changes since v2.1.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

Changes to `db_names` now reach a running cluster. A database added to the list
is created on every node and joins Spock the next time the deployment playbook
runs, including on an Ultra-HA cluster whose leaders Patroni has moved off each
zone's first node. Removing a database from the list no longer shrinks the
worker and slot pools the cluster may still need.

A zone in an Ultra-HA cluster can now grow while it runs. A node added to the
inventory with an existing zone's number joins that zone as another replica the
next time the deployment playbook runs.

Running the deployment playbook again against a deployed cluster now changes
nothing and reports nothing changed, whether or not Patroni has since moved a
zone's leader, and the end-to-end tests hold every deployment to that.

## Upgrading from v2.1.0

Playbooks and inventories written for v2.1.0 need no changes, unless they set
`db_names` to different lists on different pgEdge nodes. `init_server` now
refuses that; set `db_names` once, on the `pgedge` group.

A run whose `--limit` leaves out the node running a zone's primary now stops
rather than skipping the writes to that zone. Include each zone's primary in
the limit.

## Changes

### Added

- A node added to the inventory of an Ultra-HA zone that already runs joins
  the zone when the deployment playbook runs again. Previously `setup_etcd`
  started the new node's etcd as though bootstrapping the zone from nothing,
  and the running members refused it, so Patroni on the new node had no store
  to use. The role now asks each zone's etcd which members it has. A node with
  no data in a zone that answers is added with `etcdctl member add --learner`,
  started with the membership etcd reports, and promoted to a voting member
  once etcd judges it caught up. A learner does not count toward the zone's
  quorum, so a node that fails to start costs the zone nothing. Nodes join one
  at a time, and a run stopped partway through a join is finished by the next.
  The new member is then given the same configuration as the rest of its zone,
  and the zone's members are restarted one at a time to list it. The role
  stops the run rather than guess when a zone has data on some members, none
  of which answer, and none on the rest, or when a node with no data is still
  a started member of its zone. See
  [Joining a Running Zone](../roles/setup_etcd.md#joining-a-running-zone).
  (#67)
- The Ultra-HA end-to-end tests add a seventh node to zone 1 once everything
  else has run, and check that it joins: every member of the zone's etcd votes
  and is healthy, Patroni sees the whole zone with one leader and the new node
  streaming from it, a row written on the leader reaches it, and a second
  deployment run changes nothing. (#67)
- New `zone_primary` task file in `role_config` records, as the `zone_primary`
  fact, the node running each zone's primary: the zone's only node on a simple
  cluster, and the node Patroni reports as leader on an HA one. Only a zone
  never built takes its first node as the primary; a built zone whose Patroni
  is stopped everywhere has Patroni started on its members so they elect a
  leader, and stops the run if no member can start. Once Patroni runs, it
  stops the run unless Patroni reports exactly
  one leader among the zone's nodes and every node agrees which. It also stops
  the run when the primary is not among the play's hosts, as when `--limit`
  leaves it out. `setup_postgres` and `setup_pgedge` use it to
  choose where to write, and `finalize_backrest` uses it in place of the
  lookup it kept to itself. See
  [Zone Primary](../roles/role_config.md#zone-primary). (EE-44)
- New `sizing_floor` task file in `role_config` reads back the
  `max_worker_processes`, `max_replication_slots`, `max_wal_senders` and
  `max_active_replication_origins` each zone was last configured with, from
  `patroni.yml` on Ultra-HA and `postgresql.conf` otherwise, into the
  `pg_sizing_floor` fact that the calculated sizes never go below. It reads
  files rather than the running server, so it works whether or not Postgres
  is up. See [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)
- New `unmanaged_db_names` parameter lists databases that run on the cluster
  but that the collection does not manage: one removed from `db_names` and
  kept replicating, or one created by hand. The worker and slot formulas count
  each as a database that replicates, but the collection does nothing else
  with them. Without it, the sizing floor kept a removed database's share of
  the pools only until another database was added to `db_names`, which the
  formula then counted in its place, leaving too few workers and slots for
  both. `init_server` refuses a name listed in `unmanaged_db_names` and
  `db_names` both, or `coldfront_db` where ColdFront is enabled, which the
  sizing already counts. See
  [unmanaged_db_names](../configuration/cluster.md#unmanaged_db_names).
  (EE-44)

- `init_server` refuses an inventory whose pgEdge nodes do not all list the
  same databases in `db_names`, and likewise in `unmanaged_db_names`. Spock
  subscribes each database in `db_names` to the same database on every other
  node, so a node with a different list either subscribes to databases its
  peers never create or leaves out ones they replicate, and every node's
  worker and slot pools are sized for every database. The order of the names
  does not matter, and a node that leaves `db_names` unset counts as having
  its default. The refusal names each differing list and the nodes that hold
  it. (EE-44)

### Fixed

- `max_worker_processes` counts the Spock manager worker in `coldfront_db`
  where ColdFront is enabled outside mesh mode. Spock starts one in every
  database that accepts connections, but the formula counted only the
  databases in `db_names`, which outside mesh mode do not include
  `coldfront_db`, leaving one worker fewer than the cluster needs. (EE-44)

- A database added to `db_names` now reaches a running cluster when the
  deployment playbook runs again. Each node gets the database and the Spock and
  Snowflake extensions, client authentication rules that name it, and Spock
  subscriptions to every other zone's copy of it. Previously, an Ultra-HA
  cluster whose leaders Patroni had moved off each zone's first node failed
  outright: `setup_postgres` tried to create the database on a read-only
  replica, and `setup_patroni` waited for the first node to report itself
  running, which a Patroni replica never does. Even with the leaders in place,
  `setup_patroni` rewrote `patroni.yml` without reloading Patroni, so the new
  database stayed closed to subscriptions arriving through the other zones'
  proxies. A simple cluster had the same gap whenever the new database left
  the worker and slot sizing unchanged, because `setup_postgres` reloaded
  Postgres only for a changed `postgresql.conf`. (EE-44)
- Removing a database from `db_names` no longer shrinks the calculated
  `max_worker_processes`, `max_replication_slots`, `max_wal_senders` and
  `max_active_replication_origins` beneath what the running cluster still uses.
  The collection never drops a database, its Spock node or its subscriptions,
  so sizing from `db_names` alone left the pools too small after the next
  restart: Spock could not start the workers it needed, and Postgres refused to
  start when it held more slots than `max_replication_slots` allowed. Each run
  now sizes the pools no smaller than each zone was last configured with, so
  the calculated sizes only ever go up. Setting them in `pg_parameters` still
  replaces the calculation, which is how to lower them. See
  [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)
- The configuration reference now says what removing a name from `db_names`
  means: the collection stops managing the database but does not drop it. It
  lists what the database no longer gets, including its `pg_hba` rules, which
  stops its replication the next time a subscription reconnects. Because
  `spock.sub_drop` cannot then reach the provider to drop the subscription's
  slot, it gives the order in which to retire a database before removing its
  name, and how `custom_hba_rules` reopens access to one already removed. See
  [Removing a database from
  db_names](../configuration/cluster.md#removing-a-database-from-db_names).
  (EE-44)
- `setup_patroni` reloads Patroni on a node where it was already running and
  `patroni.yml` changed, and waits for the zone's leader, wherever it is,
  rather than for the first node. (EE-44)
- `setup_postgres` no longer edits `pg_hba.conf` or `postgresql.conf` on a node
  Patroni already manages. It used to rewrite Patroni's `pg_hba.conf` on every
  run with rules missing the proxies' access to the databases in `db_names`,
  which took effect the next time anything reloaded Postgres. (EE-44)
- The end-to-end tests run `tests/playbooks/db-add.yml` against both
  scenarios, except with ColdFront. On Ultra-HA it first moves each zone's
  leader to the zone's second node. It then adds a database, checks that it
  exists on every node and that a row written in one zone reaches every other.
  It takes the name back out of `db_names` while the database still replicates
  and checks that every node keeps the pools the database needs, then drops it,
  checks that the pools return to what the deployment needs, and puts the
  leaders back. (EE-44)
- Running the deployment playbook a second time against a deployed cluster
  reports no changes. Previously every run reported several on each pgEdge
  node, which hid any real change among them:
  - Spock's node and subscription tasks reported a change whether or not they
    created anything. They now report one only when they do.
  - The wait for a zone's Patroni leader reported a change every time.
  - `setup_postgres` rebuilds `pg_hba.conf` on every run of a node Patroni
    does not manage, and every rule it wrote reported a change. Only a file
    that ends up different now does, which is also what decides the reload.
  - On Debian, `setup_postgres` set the configuration directory in
    `/etc/postgresql` to mode `0700`, and `pg_createcluster` set it back to
    Debian's `0755` when it created the cluster, and again whenever Patroni
    cloned a replica. Each run then reported closing it. `setup_postgres` now
    leaves the directory's mode to `pg_createcluster`, and the files in it keep
    their own. On RHEL the configuration directory is the data directory,
    which stays `0700`.
  - In SSH mode, the backup servers' and pgEdge nodes' `known_hosts` entries
    for each other were taken from `ssh-keyscan`, run on the controller, and
    handed over in whatever order its keys arrived, which changes from one
    scan to the next. Each run could replace an entry, and a scan refused while
    every fork scanned the same host failed the run. Each host's ed25519 key
    now comes from the facts the deployment gathers; only a `backup_host`
    outside the inventory is still scanned, for that one key.
  - Refreshing the APT cache no longer reports a change.
  (EE-49)
- A changed `pgedge_password`, `replication_password` or `backup_password`
  now reaches the `.pgpass` file that uses it. The entry was only ever
  appended, and libpq takes the first entry that matches, so the old password
  kept being used: Spock's subscriptions failed to authenticate the next time
  they reconnected. Each entry is now written by a new `pgpass_entry` task
  file in `role_config`, which first removes any entry for the role with a
  different password, including duplicates earlier runs left behind, and
  escapes colons and backslashes as `.pgpass` requires. A password containing
  either was previously written in a form libpq could not match. (EE-49)
- On a simple cluster with a backup repository, the backup server's
  `pg_hba.conf` rules were added by `finalize_backrest` after `setup_postgres`
  had rebuilt the file without them. Each later run removed them, reloaded
  Postgres, added them back and reloaded again, refusing the backup server in
  between. `setup_postgres` now writes them with the rest, and
  `finalize_backrest` no longer edits `pg_hba.conf`. (EE-49)
- Every HA node now has the replication user's `.pgpass` entry, rather than
  only the zone's primary. Written only there, it was added to each node the
  first time a failover made that node the leader. (EE-49)
- Several steps that took a zone's first node for its primary now use
  `zone_primary`, so a run after a failover or switchover behaves as one before
  it (EE-49):
  - The backup server reads the cluster's timeline from the zone's primary.
    A replica's checkpoint moves to a new timeline only at its next
    restartpoint, so after a failover the first node could still report the
    old one, and a backup already taken on the new timeline looked
    unrestorable. The run then took a full backup, which with
    `full_backup_count` at 1 expired the previous one.
  - The check that a repository does not already hold the cluster runs on the
    zone's primary. Run on the first node, it refused a first node that had
    become a replica and been wiped for Patroni to clone again, which is the
    empty data directory beside a full repository that a replica has by
    design.
  - `finalize_backrest` checks the repository's identity and points Patroni
    at the repository from the zone's primary.
- `setup_patroni` forces a restart of a first node it starts only when that
  start bootstraps the zone. A first node rejoining a built zone as a replica,
  as after a failover, is restarted only when it has a restart pending and
  `pg_allow_restart` allows it. (EE-49)
- `recover_postgres` can restore a cluster whose worker or connection pools
  grew after the backup it restores, as they do when a database is added to
  `db_names`. Postgres refuses to replay WAL written by a server whose
  `max_worker_processes`, `max_wal_senders`, `max_connections`,
  `max_prepared_transactions` or `max_locks_per_transaction` was larger than
  its own. The restored node replayed with the pools in its configuration
  file: on RHEL the backup's own, which recovery paused on at the first larger
  record, and on Debian Postgres's defaults, which aborted at once. The
  restored node now replays with `hot_standby` off, where Postgres makes no
  such check, and starts with the pool sizes a deployment would give its
  zone. (EE-49)
- `tests/check-idempotence.sh` runs the whole deployment playbook a second
  time, rather than only the pooler roles, and fails if any task reports a
  change. The end-to-end tests also run it on Ultra-HA after moving each
  zone's leader to the zone's second node with the new
  `tests/playbooks/move-leaders.yml`, which then moves them back. (EE-49)
