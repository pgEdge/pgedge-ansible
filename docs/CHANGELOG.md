# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- New `patroni_dcs` parameter selects the distributed configuration store
  Patroni uses and passes arbitrary connection settings to it, allowing an
  externally managed store such as Consul or ZooKeeper. Accepted types are
  `etcd3`, `etcd`, `consul`, `zookeeper`, and `exhibitor`. Patroni's
  `kubernetes` type is not accepted, because it discovers the API server from
  a pod environment or a kubeconfig rather than from a configured endpoint,
  and this collection installs Patroni on ordinary hosts. (EE-33)
- `install_patroni` now installs the Patroni client library that matches the
  configured `patroni_dcs` type. (EE-33)
- Ultra-HA end-to-end test now covers an externally managed Consul store in
  addition to the default etcd cluster. (EE-33)
- New `patroni_namespace` parameter sets the key prefix Patroni uses within
  the distributed configuration store, so a store shared by more than one zone
  can give each zone its own prefix. Defaults to `/db/`, which matches the
  previous hardcoded value. (EE-33)
- New `patroni_scope` parameter sets the cluster name Patroni uses within the
  distributed configuration store, so a store shared by more than one zone can
  give each zone its own scope instead of its own namespace prefix, which some
  stores make load-bearing. Defaults to `<pg_version>-<cluster_name>`, which
  matches the previous hardcoded value, and the `patronictl` invocations in
  `setup_patroni` and `setup_backrest` now name the cluster with it. (EE-33)
- `init_server` now asserts that `patroni_dcs.parameters` is present when
  `patroni_dcs.type` names a store the collection does not deploy, so a
  missing key fails before bootstrapping rather than while Patroni is
  configured. (EE-33)
- `role_config` gained a `pg_feature_checks` task file that asks the installed
  PostgreSQL binary which configuration parameters it recognizes.
  `setup_postgres` and `setup_patroni` include it so configuration can be
  gated on parameters that only some releases carry. (EE-34)
- New `install_pgbouncer` and `setup_pgbouncer` roles deploy a pgBouncer
  connection pooler on pgEdge nodes, giving each node a second endpoint on
  `pgbouncer_port` beside PostgreSQL's own. Pooling is opt-in through the new
  `pgbouncer_enabled` parameter, which is cluster-wide the way `is_ha_cluster`
  is: set it on the `pgedge` group and every node pools, leave it unset and
  the cluster renders exactly the configuration it did before. `init_server`
  rejects an inventory whose pgEdge nodes disagree, because a zone that pooled
  only some of its nodes would lose its pooled endpoint on the first failover
  to one of the others.
- Pooled connections authenticate through pgBouncer's `auth_query` rather than
  a maintained password list. `setup_postgres` creates a powerless
  `pgbouncer_auth` role and a `SECURITY DEFINER` lookup wherever the cluster
  pools, so every PostgreSQL role works through the pooled endpoint, including
  roles created after deployment, and a rotated password takes effect
  immediately. The lookup filters on the role's `VALID UNTIL`, so an expired
  password is refused at the pooler instead of being accepted there and failing
  the backend login. Only `pgbouncer_auth_password` is written to disk, and
  `init_server` refuses to deploy a pooled cluster while it is still the
  default.
- The pooler enforces its own client authentication rules, rendered into
  `/etc/pgbouncer/pg_hba.conf` from the same variables that drive the
  PostgreSQL rules. `custom_hba_rules` admits a client to both endpoints; the
  new `pgbouncer_hba_rules` admits it to the pooled endpoint alone.
  `init_server` validates both against the `pg_hba` subset pgBouncer can
  parse, since it skips a line it cannot parse rather than refusing to start.
  `pgbouncer_auth` reaches the pooler over its unix socket only: the rendered
  rules reject it on every address, ahead of the loopback and proxy rules that
  name every role, so the one account that can read stored verifiers is not
  also a network login.
- The pooled endpoint serves TLS from the same certificate PostgreSQL
  presents, staged from the controller rather than read out of `PGDATA` so an
  HA replica does not race Patroni's clone.
  `pgbouncer_client_tls_sslmode` defaults to `allow`, which accepts exactly
  what the direct endpoint accepts today.
- New `pooler_port` parameter fronts the poolers from the proxy layer, the way
  `proxy_port` fronts `pg_port`. Where the cluster pools, `setup_haproxy`
  emits a `pg-pooler` listener on it carrying every node of the zone — the
  same servers as the direct listener, differing only in the port —
  health-checked against Patroni's REST API like the direct listeners, and
  sizes the global connection ceiling to cover it. The existing listeners are
  unchanged, so Spock replication never routes through a pooler. `init_server`
  asserts the ports a host actually binds do not collide: the two proxy-layer
  ports against each other on any HAProxy node, and against `pg_port` and
  `pgbouncer_port` only where HAProxy shares a host with a pgEdge node, since
  that is the only topology where all four bind the same address.
- New documentation for pooling: role pages for both new roles, a Pooling
  Configuration reference, a pgBouncer troubleshooting page, the pooled
  listener and the port model in Proxy Configuration, `pgbouncer_enabled` in
  Inventory Structure, and an opt-in walkthrough in both tutorials.

### Fixed

- Spock replication no longer breaks on PostgreSQL releases carrying the fix
  for CVE-2026-6471, which refuse to load an output plugin that
  `output_plugin_libraries` does not name. Both simple and Ultra-HA clusters
  now set the parameter, and only on releases that recognize it, since earlier
  releases refuse to start when it appears. (EE-34)
- `init_server` now rejects an inventory that gives `proxy_port` the same value
  as `pg_port` on a host that runs HAProxy alongside a pgEdge node, a topology
  the proxy documentation supports. HAProxy could not bind its listener there,
  which surfaced as a service failure well after the playbook had configured
  the node rather than as a validation error before it started.
- `patroni_config_file` and `patroni_tls_dir` are now recognized by all roles.
- HA failover example in the usage guide now passes the Patroni scope the
  collection actually configures, which has included the PostgreSQL version
  since v1.0.0.
- Patroni replication user now connects to all databases for logical slot
  creation.
- `backup_repo_cipher` default is now properly deterministic.
- PostgreSQL contrib package is now installed explicitly on RHEL systems where
  it may be missing.

## v1.0.0

This release is a major overhaul that revises every role in the collection.
It replaces the pgEdge CLI component with standard RPM and DEB packages from
the pgEdge and PGDG package repositories. All local-user installation
semantics are removed in favor of the standard `postgres` OS user and
system-conventional paths.

**This is a breaking change.** Clusters deployed with v0.1 or v0.2 cannot be
upgraded in place. Re-provision all nodes from scratch before deploying to
production.

### Added

- New `install_repos` role installs the pgEdge and PGDG package repositories
  on each node before any software installation takes place. Add this role to
  all playbooks immediately after `init_server`. (EE-22)
- `custom_hba_rules` parameter accepts a list of custom `pg_hba.conf` rules
  to append to the default rule set.
- `backup_user` and `backup_password` parameters define a dedicated
  PostgreSQL user with `pg_checkpoint` privileges for backup operations.
- `backup_repo_user` parameter specifies the OS user that owns the PgBackRest
  repository in SSH backup mode.
- `proxy_port` parameter allows HAProxy to run on a pgEdge node by setting a
  proxy port separate from the PostgreSQL listen port.
- `pgedge_user` and `pgedge_password` parameters define the internal user
  used for node-to-node Spock connections.
- `tls_validity_days` parameter controls the validity period for generated
  TLS certificates.

### Fixed

- Patroni cluster initialization now waits for the primary to become
  available before performing administrative operations.

### Changed

- Switched to pgEdge distro-specific package repositories; `repo_name`
  default changed from `download` to `release`. (EE-22)
- PostgreSQL, etcd, Patroni, and PgBackRest are now installed from system
  packages rather than downloaded locally. The `install_base` and
  `cluster_path` parameters are removed.
- PostgreSQL now runs as the system `postgres` user. Data and configuration
  directories follow OS conventions: `/var/lib/postgresql/VERSION/main` and
  `/etc/postgresql/VERSION/CLUSTER` on Debian; `/var/lib/pgsql/VERSION/data`
  on RHEL.
- `pg_home`, `pg_path`, `pg_data`, and `pg_config_dir` are now computed
  from `pg_version` and OS family. The `cluster_path`-based path variables
  are removed.
- Default `pg_hba.conf` rules now use a least-privilege model and only
  include entries for known user and database combinations. Custom rules can
  be added via `custom_hba_rules`.
- `init_server` now disables `RemoveIPC` in systemd-logind, creates the
  `postgres` OS user on nodes that require SSH backup access, and validates
  configuration before any other tasks run.
- Updated default etcd version to 3.6.5.
- Spock extension is now always installed at the latest available version.
- Several parameters previously scattered across role defaults are now
  centralized in the `role_config` role.

## v0.2.0

### Added

- Ability to specify additional HAProxy listeners for specific Patroni node types. (EE-9)
- Restart Postgres in setup_patroni role to activate config changes. (EE-13)

### Changed

- Switched to upstream etcd and Patroni releases. (EE-15)
- Set default Spock version to 5.0.
- Set default Postgres version to 17.

## v0.1.0

The "real" release.

### Added

- Ability to specify multiple database names for subscription management. (EE-12)
- Ability to specify exception_behaviour as parameter. (EE-7)
- Can now specify proxy_node to override automatic haproxy zone target. (EE-3)

### Fixed

- Additional retries to circumvent Debian package management locks. (#15)
- replication_user and replication_password actually work now. (EE-14)
- Strip comments from ssh_keyscan output to avoid syntax errors. (#13)
- DDL replication now activates spock.allow_ddl_from_functions. (EE-10)
- Added lock_timeout parameter to all package tasks to avoid failures. (EE-8)
- Added explicit dependency to ansible.utils.ipaddr filter. (EE-1)

### Changed

- Renamed db_name role parameter to db_names to list multiple database names. (EE-12)

## v0.0.2

### Added

- Initial creation and setup roles for pgEdge cluster resources.
