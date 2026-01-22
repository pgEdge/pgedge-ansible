# Release Notes

This file documents all notable changes to the pgEdge Ansible Collection.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.0.0

This major release revises every role in the collection. The update replaces
the CLI component with standard RPM and DEB packages; this change removes all
local-user installation semantics in favor of the standard `postgres` OS user.

### Added

- Custom `pg_hba.conf` rules allow fine-grained access control.
- A dedicated backup user provides specific access controls for backup ops.
- A repository-specific user enables SSH backup mode authentication.
- HAProxy can now run on pgEdge nodes by specifying a separate port.
- Full mkdocs site documentation covers all collection features.

### Fixed

- Patroni cluster establishment now completes before admin operations begin.

### Changed

- The collection now uses pgEdge distro-specific package repositories. (EE-22)
- The default etcd version now targets 3.6.5 for latest features and fixes.
- The collection now always installs the latest Spock extension.
- Several default variables moved into role_config for wider availability.
- Default `pg_hba.conf` rules now only reflect known user/db combinations.
- This release removes the `cluster_path` parameter and all related paths.
- Multiple default values now better fit package-based installation.

## v0.2.0

### Added

- Additional HAProxy listeners support specific Patroni node types. (EE-9)
- The setup_patroni role restarts Postgres to activate config changes. (EE-13)

### Changed

- The collection now uses upstream etcd and Patroni releases. (EE-15)
- The default Spock version now targets 5.0 for latest features.
- The default Postgres version now targets 17 for latest features.

## v0.1.0

This release represents the first production-ready version.

### Added

- Multiple database names support for subscription management. (EE-12)
- The `exception_behaviour` parameter allows customization. (EE-7)
- The `proxy_node` parameter overrides automatic HAProxy zone target. (EE-3)

### Fixed

- Additional retries circumvent Debian package management locks. (#15)
- The `replication_user` and `replication_password` parameters work. (EE-14)
- SSH keyscan output now strips comments to avoid syntax errors. (#13)
- DDL replication now activates `spock.allow_ddl_from_functions`. (EE-10)
- All package tasks now include a lock timeout parameter to avoid failures. (EE-8)
- The collection now declares explicit dependency on ansible.utils.ipaddr. (EE-1)

### Changed

- The `db_name` parameter now uses `db_names` for multiple databases. (EE-12)

## v0.0.2

This release marks the initial open-source publication.

### Added

- Initial creation and setup roles for pgEdge cluster resources.
