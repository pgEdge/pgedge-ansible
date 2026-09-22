# Unreleased

These notes describe the changes since v2.0.0.
The [Changelog](../CHANGELOG.md) summarizes them.

## Changes

### Added

- New `install_coldfront` and `setup_coldfront` roles add ColdFront tiered
  storage to a pgEdge Distributed Postgres node. Recent data stays in native
  Postgres partitions, and older data archives to Iceberg tables on
  S3-compatible storage. New `install_lakekeeper` and `setup_lakekeeper` roles
  build Lakekeeper, the Iceberg REST catalog ColdFront commits through, on a
  host of its own with a Postgres instance for the catalog. On a later run,
  `setup_lakekeeper` updates the warehouse's storage profile where it differs
  from the `coldfront_s3_*` settings, sending the credential with it, and
  restarts Lakekeeper when its environment file is newer than the process.
  Lakekeeper does not return the stored credential, so a changed access key
  or secret key alone does not reach the warehouse. (EE-40)
- New `coldfront_enabled` parameter adds `pg_duckdb` and `coldfront` to
  `shared_preload_libraries`, and ColdFront's settings to the Postgres
  configuration `setup_postgres` writes. `setup_postgres` applies them like
  any other parameter, restarting one node at a time where `pg_allow_restart`
  allows, then checks that the libraries have loaded and creates ColdFront's
  role, database and extensions. They are parameters the collection
  controls, so `init_server` refuses `pg_parameters` that sets them.
  `install_coldfront` runs before `setup_postgres`, and the sample and test
  playbooks run `install_coldfront` and `setup_coldfront` only where
  `coldfront_enabled` is set. See
  [ColdFront Configuration](../configuration/coldfront.md). (EE-40)
- New `lakekeeper_*` and `coldfront_s3_*` parameters locate the catalog and
  the S3-compatible object store behind the cold tier. Any S3-compatible
  store works, and the collection deploys none. (EE-40)
- `init_server` refuses `coldfront_enabled` on an HA cluster, without
  `lakekeeper_host`, without a bucket, region, access key and secret key for
  the object store, with a `coldfront_s3_endpoint` that is not an
  `http(s)://host[:port]` URL, or with a `pg_version` outside
  `coldfront_supported_pg_versions`. It refuses a Lakekeeper host whose
  `lakekeeper_db_password` is still the default, whose `pg_port`,
  `lakekeeper_port` and `lakekeeper_metrics_port` collide, or that is also in
  the `pgedge` group. Like every other host, the Lakekeeper host runs
  `init_server` first. (EE-40)
- The `sample-playbooks/simple-cluster/` playbook sets up ColdFront and its
  Lakekeeper host in the same run where `coldfront_enabled` is set, with a play
  for the `lakekeeper` group and the two ColdFront roles gated on
  `coldfront_enabled`, and its inventory shows the settings. The simple-cluster
  end-to-end test takes ColdFront as a layer: `tests/run-test.sh ... coldfront`,
  or the workflow's `coldfront` input, adds a Lakekeeper host and a SeaweedFS
  object store from `tests/compose/coldfront-*.yml` and
  `tests/inventories/coldfront.yml`. It then checks that the catalog serves its
  warehouse, that ColdFront's libraries load beside Spock and Snowflake, and
  that a decoupled Iceberg table accepts a write and returns it.
  `tests/render/check-patroni.py` checks ColdFront's parameter layer, and
  `tests/render/check-validate.py` checks `init_server`'s refusals.
  `tests/playbooks/coldfront-reconfigure.yml`, run with the layer, checks that
  re-applying the ColdFront and Lakekeeper roles changes nothing, and that
  turning ColdFront off and on again on a running cluster restarts each node to
  load or unload its libraries. (EE-40)
- `setup_postgres` gained a `plain_instance` task file for roles that need a
  Postgres instance of their own rather than a pgEdge Distributed Postgres
  node, used by `setup_lakekeeper`. It creates the instance with the same
  tasks `setup_postgres` uses for a node. On Debian, `pg_createcluster` is now
  given `pg_port`, which the node's configuration already set afterwards.
  (EE-40)
- `coldfront_mesh: true` has ColdFront order cold-tier commits across every
  node of a Spock cluster, following upstream's mesh setup. It needs
  `coldfront_db` in `db_names`, which `init_server` checks, so that
  `setup_postgres` and `setup_pgedge` put the ColdFront database into Spock
  and the worker and slot sizing counts it. Mesh mode adds
  `coldfront.dblink_self`, `coldfront.peer_alive_window_ms` and
  `wal_receiver_status_interval` to ColdFront's parameters. `setup_postgres`
  creates the `dblink` extension with ColdFront's others, before
  `setup_pgedge` puts the database into Spock. `setup_coldfront` adds
  ColdFront's bakery and catalog tables to Spock's `default` replication set,
  and sets the storage secret on the first pgEdge node only, since Spock
  carries it to the others. The new
  `coldfront_peer_alive_window_ms` parameter sets how long the bakery waits
  on a peer that reports no replication progress. The simple-cluster
  end-to-end test runs ColdFront in mesh mode with
  `tests/run-test.sh ... coldfront mesh` or the workflow's `mesh` input, and
  then checks that the bakery is armed and its tables replicate, and has every
  node write to one table at once. (EE-40)
