# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

This release is a major overhaul that revises every role in the collection.
It replaces the pgEdge CLI component with standard RPM and DEB packages from
the pgEdge and PGDG package repositories. All local-user installation
semantics are removed in favor of the standard `postgres` OS user and
system-conventional paths.

**This is a breaking change.** Clusters deployed with v0.2 cannot be upgraded
in place. Re-provision all nodes from scratch before deploying to production.

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
