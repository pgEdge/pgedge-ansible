# Unreleased

These notes describe the changes since v2.0.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

This release adds ColdFront tiered storage to pgEdge Distributed Postgres
clusters. ColdFront keeps recent data in native Postgres partitions and
archives older data to Apache Iceberg tables on S3-compatible storage,
readable and writable through the same SQL.

Its main features are:

- New `install_coldfront`, `setup_coldfront_db` and `setup_coldfront` roles
  that add ColdFront to the pgEdge nodes, and new `install_lakekeeper` and
  `setup_lakekeeper` roles that build the Lakekeeper Iceberg catalog it
  commits through, on a host of its own.
- A mesh mode that orders cold-tier commits across every node of a Spock
  cluster. ColdFront also runs on Ultra-HA clusters, which require mesh mode.
- New `simple-cluster-coldfront` and `ultra-ha-coldfront` sample playbooks
  and inventories. See
  [ColdFront Configuration](../configuration/coldfront.md).

## Upgrading from v2.0.0

ColdFront is optional, and nothing changes for a cluster that does not set
`coldfront_enabled`. Playbooks and inventories written for v2.0.0 need no
changes.

## Changes

### Added

- New `install_coldfront` and `setup_coldfront` roles add ColdFront tiered
  storage to a pgEdge Distributed Postgres node. Recent data stays in native
  Postgres partitions, and older data archives to Iceberg tables on
  S3-compatible storage. New `install_lakekeeper` and `setup_lakekeeper` roles
  build Lakekeeper, the Iceberg REST catalog ColdFront commits through, on a
  host of its own with a Postgres instance for the catalog, which
  `setup_lakekeeper` initializes and runs as its own `lakekeeper-postgres`
  service. On a later run, `setup_lakekeeper` updates the warehouse's storage
  profile where it differs from the `coldfront_s3_*` settings, sending the
  credential with it, and restarts Lakekeeper when its environment file is
  newer than the process. Lakekeeper does not return the stored credential, so
  a changed access key or secret key alone does not reach the warehouse.
  (EE-40)
- New `coldfront_enabled` parameter adds `pg_duckdb` and `coldfront` to
  `shared_preload_libraries`, and ColdFront's settings to the Postgres
  configuration `setup_postgres` writes. `setup_postgres` applies them like any
  other parameter, restarting one node at a time where `pg_allow_restart`
  allows. The new `setup_coldfront_db` role then checks that the libraries have
  loaded and creates ColdFront's role, database and extensions. The settings
  ColdFront depends on are parameters the collection controls, so `init_server`
  refuses `pg_parameters` that sets them; its tuning settings are defaults
  `pg_parameters` may override. `install_coldfront` runs before
  `setup_postgres`, and `setup_coldfront_db` after it. The test playbooks run
  the ColdFront roles only where `coldfront_enabled` is set, and the ColdFront
  sample playbooks always. See
  [ColdFront Configuration](../configuration/coldfront.md). (EE-40)
- New `lakekeeper_*` and `coldfront_s3_*` parameters locate the catalog and the
  S3-compatible object store behind the cold tier. Any S3-compatible store
  works, and the collection deploys none. (EE-40)
- `init_server` refuses `coldfront_enabled` on an HA cluster without
  `coldfront_mesh`, without `lakekeeper_host`, without a bucket, region, access
  key and secret key for the object store, with a `coldfront_s3_endpoint` that
  is not an `http(s)://host[:port]` URL, or with a `pg_version` outside
  `coldfront_supported_pg_versions`. It refuses a Lakekeeper host whose
  `lakekeeper_db_password` is still the default, whose `pg_port`,
  `lakekeeper_port` and `lakekeeper_metrics_port` collide, or that is also in
  the `pgedge` group. Like every other host, the Lakekeeper host runs
  `init_server` first. (EE-40)
- The new `sample-playbooks/simple-cluster-coldfront/` playbook sets up a
  simple cluster with ColdFront and its Lakekeeper host in the same run, with a
  play for the `lakekeeper` group and the ColdFront roles in the `pgedge` play,
  and its inventory shows the settings. ColdFront is optional, so the plain
  `simple-cluster` sample leaves it out. The simple-cluster end-to-end test
  takes ColdFront as a layer, deploying with the ColdFront sample playbook:
  `tests/run-test.sh ... coldfront`, or the workflow's `coldfront` input, adds
  a Lakekeeper host and a SeaweedFS object store from
  `tests/compose/coldfront-*.yml` and `tests/inventories/coldfront.yml`. It
  then checks that the catalog serves its warehouse, that ColdFront's libraries
  load beside Spock and Snowflake, and that a decoupled Iceberg table accepts a
  write and returns it. `tests/render/check-patroni.py` checks ColdFront's
  parameter layer, and `tests/render/check-validate.py` checks `init_server`'s
  refusals. `tests/playbooks/coldfront-reconfigure.yml`, run with the layer,
  checks that re-applying the ColdFront and Lakekeeper roles changes nothing,
  and that turning ColdFront off and on again on a running cluster restarts
  each node to load or unload its libraries. (EE-40)
- `coldfront_mesh: true` has ColdFront order cold-tier commits across every
  node of a Spock cluster, following upstream's mesh setup. It needs
  `coldfront_db` in `db_names`, which `init_server` checks, so that
  `setup_postgres` and `setup_pgedge` put the ColdFront database into Spock and
  the worker and slot sizing counts it. Mesh mode adds `coldfront.dblink_self`
  to ColdFront's parameters, and `coldfront.peer_alive_window_ms` and
  `wal_receiver_status_interval` to its tuning defaults. `setup_coldfront_db`
  creates the `dblink` extension with ColdFront's others, before `setup_pgedge`
  puts the database into Spock. `setup_coldfront` adds ColdFront's bakery and
  catalog tables to Spock's `default` replication set, and sets the storage
  secret on the first pgEdge node only, since Spock carries it to the others.
  `coldfront.peer_alive_window_ms` sets how long the bakery waits on a peer
  that reports no replication progress. The simple-cluster end-to-end test runs
  ColdFront in mesh mode with `tests/run-test.sh ... coldfront mesh` or the
  workflow's `mesh` input, and then checks that the bakery is armed and its
  tables replicate, and has every node write to one table at once. (EE-40)
- ColdFront runs on HA clusters in mesh mode. Its libraries and settings reach
  every member through the zone's Patroni configuration, which `setup_patroni`
  keeps up to date with the rest of the parameters. `setup_coldfront` asks each
  node's Postgres whether it is a standby, runs its SQL on the leader only, and
  has each replica write its own DuckDB secret from the replicated
  `coldfront.storage_secret` row with `coldfront.materialize_storage_secret()`,
  since physical replication does not carry the file DuckDB keeps it in.
  `setup_coldfront_db` runs after `setup_patroni` and creates ColdFront's role,
  database and extensions on each zone's leader. The archiver, partitioner and
  compactor connect through the zone's endpoint, the one `setup_pgedge`
  subscribes through. `init_server` refuses ColdFront on an HA cluster without
  `coldfront_mesh`, since Patroni's `pg_hba` admits `db_user` through the
  zone's proxies only to the databases in `db_names`. (EE-40)
- The new `sample-playbooks/ultra-ha-coldfront/` playbook sets up an Ultra-HA
  cluster with ColdFront in mesh mode and its Lakekeeper host, and its
  inventory shows the settings. The plain `ultra-ha` sample leaves it out. The
  Ultra-HA end-to-end test takes the ColdFront layer, always in mesh mode,
  through `tests/run-test.sh ultra-ha ... coldfront` or the workflow's
  `coldfront` input. Its verification now expects ColdFront's libraries in the
  preload list where `coldfront_enabled` is set, and
  `tests/verify/verify-ultra-ha-coldfront.yml` then checks that every member,
  replicas included, loads ColdFront, has its bakery armed, replicates the
  bakery's and catalog's tables and holds the storage secret, that both zones'
  leaders can write to one table at once without losing a row, that every
  member reads every row, and that a replica refuses a cold-tier write. The
  recovery test does not run with ColdFront. (EE-40)

### Fixed

- The compatibility list in the README and the documentation names Debian 13
  (Trixie), Ubuntu 24.04 (Noble Numbat) and Ubuntu 26.04 (Resolute Raccoon)
  beside Debian 12 and Rocky Linux 9. Each passed the simple-cluster and
  Ultra-HA end-to-end tests. Ubuntu 25.04 leaves the list: it is past its end
  of life, and the pgEdge repository no longer serves it. `tests/run-test.sh`
  and `tests/run-recovery-test.sh` take the new systems as `debian13`,
  `ubuntu2404` and `ubuntu2604`; the workflows still test Debian 12 and Rocky
  Linux 9 only. (EE-47)
- The end-to-end tests install psql on the client host from PGDG, at the
  release `client_pg_version` names in the verification playbooks (18 by
  default), so the client no longer changes with the distribution under test:
  Ubuntu 26.04's own client is psql 18, which prints `\conninfo` as a table,
  and broke a check written against the one-line form earlier releases print.
  The check now accepts both. The Rocky Linux 9 test hosts build from Rocky's
  own `rockylinux/rockylinux:9` image, which follows the current 9.x release,
  rather than the Docker Hub `rockylinux:9` image, which stopped at 9.3 and
  whose PGDG repositories no longer exist. (EE-47)
