# Configuration Reference

This page provides an overview of all configuration parameters recognized by
the pgEdge Ansible Collection roles. Parameters are set as inventory variables
or playbook variables and apply across roles unless noted otherwise.

## Configuration Overview

The pgEdge Ansible Collection provides the following methods for managing
configuration:

- Inventory files define hosts and host groups for the cluster.
- Group variables set values for all hosts in a group.
- Host variables set values for individual hosts only.
- Role defaults provide fallback values defined in each role.

See the [Inventory Structure](configuration/inventory.md) page for details on
inventory format, variable precedence, and Ansible Vault usage.

## Configuration Sections

The following pages describe all available parameters organized by topic.

### [Inventory Structure](configuration/inventory.md)

Covers the inventory file format, the three host groups (`pgedge`, `haproxy`,
`backup`), variable precedence, and Ansible Vault integration.

### [Cluster Configuration](configuration/cluster.md)

Covers cluster identity and user account parameters including `cluster_name`,
`zone`, `repo_name`, `db_names`, `db_user`, `db_password`, `pgedge_user`,
`pgedge_password`, `is_ha_cluster`, `replication_user`, `replication_password`,
`synchronous_mode`, `synchronous_mode_strict`, `tls_validity_days`, and
`spock_version`.

### [Postgres Configuration](configuration/postgres.md)

Covers Postgres installation and path parameters including `pg_version`,
`pg_port`, `pg_home`, `pg_path`, `pg_data`, `custom_hba_rules`, and the
computed internal variables `pg_config_dir`, `pg_service_name`,
`patroni_service_name`, and `nodes_in_zone`.

### [Proxy Configuration](configuration/proxy.md)

Covers HAProxy and subscription routing parameters including `proxy_port`,
`proxy_node`, and `haproxy_extra_routes`.

### [Spock Configuration](configuration/spock.md)

Covers Spock logical replication behavior including the `exception_behaviour`
parameter.

### [System Configuration](configuration/system.md)

Covers host-level operating system parameters including `debug_pgedge`,
`disable_selinux`, and `manage_host_file`.

### [Backup Configuration](configuration/backup.md)

Covers all PgBackRest parameters including `backup_repo_type`, `backup_host`,
`backup_repo_user`, `backup_repo_path`, `backup_user`, `backup_password`,
`backup_repo_cipher_type`, `backup_repo_cipher`, `full_backup_count`,
`diff_backup_count`, `full_backup_schedule`, `diff_backup_schedule`, and
`backup_repo_params`.

### [etcd Configuration](configuration/etcd.md)

Covers etcd and Patroni internal parameters including `etcd_version`,
`etcd_user`, `etcd_group`, `etcd_install_dir`, `etcd_config_dir`,
`etcd_data_dir`, `etcd_tls_dir`, and `patroni_tls_dir`.
