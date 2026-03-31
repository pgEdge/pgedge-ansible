# Changelog

All notable changes to the pgEdge Ansible Collection will be
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Added redundant path environment specification for pipx-based
  executables. (EE-19)

## [0.2.0]

### Added

- Ability to specify additional HAProxy listeners for specific Patroni
  node types. (EE-9)
- Restart of PostgreSQL in the setup_patroni role to activate
  configuration changes. (EE-13)

### Changed

- Switched to upstream etcd and Patroni releases. (EE-15)
- Set default Spock version to 5.0.
- Set default PostgreSQL version to 17.

## [0.1.0]

### Added

- Ability to specify multiple database names for subscription
  management. (EE-12)
- Ability to specify exception_behaviour as a parameter. (EE-7)
- Ability to specify proxy_node to override the automatic HAProxy
  zone target. (EE-3)

### Fixed

- Additional retries to avoid Debian package management locks. (#15)
- replication_user and replication_password parameters now applied
  correctly. (EE-14)
- Stripped comments from ssh_keyscan output to avoid syntax
  errors. (#13)
- DDL replication now activates spock.allow_ddl_from_functions. (EE-10)
- Added lock_timeout parameter to all package tasks to avoid
  failures. (EE-8)
- Added explicit dependency on the ansible.utils.ipaddr filter. (EE-1)

### Changed

- Renamed the db_name role parameter to db_names to support multiple
  database names. (EE-12)

## [0.0.2]

### Added

- Initial creation and setup roles for pgEdge cluster resources.
