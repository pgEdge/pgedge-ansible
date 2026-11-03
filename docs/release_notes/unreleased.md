# Unreleased

These notes describe the changes since v2.1.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

Changes to `db_names` now reach a running cluster. A database added to the list
is created on every node and joins Spock the next time the deployment playbook
runs, including on an Ultra-HA cluster whose leaders Patroni has moved off each
zone's first node. Removing a database from the list no longer shrinks the
worker and slot pools the cluster still needs.

## Upgrading from v2.1.0

Playbooks and inventories written for v2.1.0 need no changes.

A run whose `--limit` leaves out the node running a zone's primary now stops
rather than skipping the writes to that zone. Include each zone's primary in
the limit.

## Changes

### Added

- New `zone_primary` task file in `role_config` records, as the `zone_primary`
  fact, the node running each zone's primary: the zone's only node on a simple
  cluster, and the node Patroni reports as leader on an HA one. Until Patroni
  runs anywhere in a zone, the zone is being built and its first node is the
  primary. Once Patroni runs, it stops the run unless Patroni reports exactly
  one leader among the zone's nodes and every node agrees which. It also stops
  the run when the primary is not among the play's hosts, as when `--limit`
  leaves it out. `setup_postgres` and `setup_pgedge` use it to
  choose where to write, and `finalize_backrest` uses it in place of the
  lookup it kept to itself. See
  [Zone Primary](../roles/role_config.md#zone-primary). (EE-44)
- New `sizing_floor` task file in `role_config` reads, on each zone's primary,
  the databases that accept connections, the databases other zones subscribe
  to, the replication origins Spock keeps for its subscriptions, and the
  replication slots, into the `pg_sizing_floor` fact that the worker and slot
  calculation never goes below. A built zone whose Postgres does not answer
  stops `setup_postgres` or `setup_patroni` rather than being sized blind, and
  a `pg_parameters` value below what the cluster uses is refused. See
  [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)

### Fixed

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
  now sizes the pools no smaller than what each zone's primary holds, plus
  what any database in `db_names` that nothing subscribes to yet is about to
  need, so a run that swaps one name for another sizes for both. The pools
  come down once the database itself is dropped. See
  [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)
- The configuration reference now says what removing a name from `db_names`
  means: the collection stops managing the database but does not drop it. It
  lists what the database no longer gets, including its `pg_hba` rules, which
  stops its replication the next time a subscription reconnects. See
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
