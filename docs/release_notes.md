# Release Notes

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.0.0

This is a major overhaul that revises every role in the collection. Switching the CLI component with standard RPM and DEB packages removes the CLI component entirely and all of the local-user installation semantics in favor of the standard postgres OS user.

### Added

- It's now possible to specify custom `pg_hba.conf` rules.
- New backup user and password for specific access controls.
- New backup user specific to backup repository in SSH backup mode.
- Now possible to run HAProxy on pgEdge nodes by specifying separate port.
- Full mkdocs site documentation

### Fixed

- Wait for Patroni to establish cluster before performing admin operations.

### Changed

- Switched to pgEdge distro-specific package repositories. (EE-22)
- Updated default etcd to 3.6.5.
- Now always install latest Spock extension.
- Moved several default variables into role_config role for wider use.
- Default pg_hba.conf rules now only reflect known user/db combinations.
- Removed cluster_path parameter and all related paths.
- Changed multiple default values to better fit package-based installation.

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
- Added lock_timeout paramter to all package tasks to avoid failures. (EE-8)
- Added explicit dependency to ansible.utils.ipaddr filter. (EE-1)

### Changed

- Renamed db_name role parameter to db_names to list multiple database names. (EE-12)


## v0.0.2

"Let's open-source this cool internal product!"

### Added

- Initial creation / setup roles for pgEdge cluster resources
