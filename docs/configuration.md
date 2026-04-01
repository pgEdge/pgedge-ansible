# Configuration Reference

This page describes all configuration parameters recognized by the pgEdge
Ansible Collection and provides links to detailed documentation for each
topic area.

## Configuration Sections

- [`Inventory Structure`](configuration/inventory.md) describes the inventory
  file format, host groups, variable precedence, and Ansible Vault usage.
- [`Cluster Configuration`](configuration/cluster.md) covers cluster identity,
  database names, user accounts, and HA settings.
- [`Postgres Configuration`](configuration/postgres.md) covers Postgres version,
  ports, data paths, and authentication rules.
- [`Proxy Configuration`](configuration/proxy.md) covers HAProxy routing and
  Spock subscription endpoint settings.
- [`Spock Configuration`](configuration/spock.md) covers logical replication
  exception handling.
- [`System Configuration`](configuration/system.md) covers host-level OS
  settings including SELinux, core dumps, and host file management.
- [`Backup Configuration`](configuration/backup.md) covers all PgBackRest
  repository, encryption, retention, and scheduling parameters.
- [`etcd Configuration`](configuration/etcd.md) covers etcd and Patroni
  internal path and TLS parameters.
