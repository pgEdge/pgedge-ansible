# Configuration Reference

This page lists all parameters recognized by the pgEdge Ansible
Collection roles. Parameters are set as inventory variables or
playbook variables and apply across roles unless noted otherwise.

## Cluster Identification

The following table describes parameters that identify the cluster
and its nodes:

| Parameter | Default | Description |
|-----------|---------|-------------|
| cluster_name | demo | Canonical name for the cluster, used for descriptive items and generated values. |
| zone | 1 | Zone or region for a node. Zones also serve as Snowflake node IDs; each node must have a distinct integer value. |

## Repository Configuration

The following table describes parameters that control which software
repository the collection uses:

| Parameter | Default | Description |
|-----------|---------|-------------|
| repo_name | download | Repository source. Accepted values are download, upstream, and devel. |
| repo_prefix | (none) | Custom or automated build prefix. Contact pgEdge staff for valid values. |

## Installation

The following table describes parameters that control software
installation paths and versions:

| Parameter | Default | Description |
|-----------|---------|-------------|
| install_base | Ansible user home directory | Base directory for the pgEdge CLI and all related software, including PostgreSQL binaries, data directory, and logs. Set this to the primary data mount for the server. |
| pg_version | 17 | PostgreSQL version to install. |
| spock_version | 5.0.0 | Version of the Spock extension to install. |

## Database Configuration

The following table describes parameters that control database
creation and access:

| Parameter | Default | Description |
|-----------|---------|-------------|
| db_names | [demo] | List of database names for the Spock cluster. At least one name is required. Any database in the list that does not already exist will be created and owned by db_user. |
| db_user | admin | Database superuser username. Must differ from the OS user running the installation. |
| db_password | secret | Password for db_user. |

## High Availability

The following table describes parameters that control HA behavior.
These parameters apply only when `is_ha_cluster` is `true`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| is_ha_cluster | false | When true, the collection installs and configures etcd, Patroni, and HAProxy on the appropriate nodes. |
| replication_user | replicator | Username for Patroni streaming replication. |
| replication_password | secret | Password for replication_user. |
| synchronous_mode | false | When true, Patroni manages the synchronous_commit and synchronous_standby_names PostgreSQL parameters based on cluster state. |
| synchronous_mode_strict | false | When synchronous_mode is enabled, Patroni disables synchronous replication if no synchronous replicas are available. Set this to true to always enforce synchronous commit regardless of replica availability. |
| proxy_node | (none) | Overrides automatic HAProxy target selection for Spock subscriptions. When unset, subscriptions target the first HAProxy node in the same zone as the remote pgEdge node, or the first pgEdge node in that zone if no HAProxy node is present. |

## HAProxy

The following table describes parameters that control HAProxy
configuration:

| Parameter | Default | Description |
|-----------|---------|-------------|
| haproxy_extra_routes | {replica: {port: 5433}} | Additional HAProxy listeners corresponding to [Patroni REST endpoint](https://patroni.readthedocs.io/en/latest/rest_api.html) check types. Each entry requires a port sub-key and accepts an optional lag sub-key for maximum replica lag. |

## Server Configuration

The following table describes parameters that control server-level
behavior:

| Parameter | Default | Description |
|-----------|---------|-------------|
| debug_pgedge | true | When true, configures kernel settings to retain core files produced during a process crash. |
| manage_host_file | true | When true, adds all cluster nodes to the /etc/hosts file on every node. Set to false when external DNS is in use or when inventory hostnames are IP addresses. |

## Backup Configuration

The following table describes parameters that control PgBackRest
backup behavior:

| Parameter | Default | Description |
|-----------|---------|-------------|
| backup_host | (none) | Hostname of the dedicated backup server. When empty and backup_repo_type is ssh, the first node in the backup host group in the same zone is used. |
| backup_repo_type | ssh | Backup repository type. Accepted values are ssh (dedicated backup server) and s3 (AWS S3 bucket). |
| backup_repo_path | cluster_path/data/backrest | Full path to the PgBackRest repository. For S3 repositories, use a simple path such as /backrest. |
| backup_repo_cipher_type | aes-256-cbc | Encryption algorithm for backup files stored in the PgBackRest repository. |
| backup_repo_cipher | (generated) | Encryption password for backup files. When unset, a 20-character deterministic random string is generated from the repository name. |
| full_backup_count | 1 | Number of full backups to retain in the repository. |
| diff_backup_count | 6 | Number of differential backups to retain in the repository. |
| full_backup_schedule | 10 0 * * 0 | Cron schedule for full backups. The default runs every Sunday at 00:10 UTC. |
| diff_backup_schedule | 10 0 * * 1-6 | Cron schedule for differential backups. The default runs Monday through Saturday at 00:10 UTC. |
| backup_repo_params | (see below) | Dictionary of S3 repository parameters. Required when backup_repo_type is s3. |

The `backup_repo_params` dictionary accepts the following keys with
the defaults shown:

```yaml
backup_repo_params:
  region: us-east-1
  endpoint: s3.amazonaws.com
  bucket: pgbackrest
  access_key: ''
  secret_key: ''
```

## Spock Configuration

The following table describes parameters that control Spock logical
replication behavior:

| Parameter | Default | Description |
|-----------|---------|-------------|
| exception_behaviour | transdiscard | How Spock handles replication exceptions. Accepted values are discard, transdiscard, and sub_disable. See the [pgEdge exception documentation](https://docs.pgedge.com/platform/exception#spockexception_behaviour) for details. |

## Internal Variables

The following table describes internal variables computed by the
`role_config` role. These variables are available for reference when
modifying or extending the collection roles:

| Variable | Value | Description |
|----------|-------|-------------|
| repo_url | https://pgedge-REPO.s3.amazonaws.com/REPO | Constructed S3 URL for package downloads, based on repo_name. |
| cluster_path | HOME/pgedge | Default installation root for the pgEdge CLI and all related files. |
| pg_path | cluster_path/pgVERSION | Path to PostgreSQL binaries. For PostgreSQL 17 this is cluster_path/pg17. |
| pg_data | cluster_path/data/pgVERSION | Path to the PostgreSQL data directory. For PostgreSQL 17 this is cluster_path/data/pg17. |
| nodes_in_zone | (computed) | List of all nodes in the pgedge host group that share the same zone as the current node. Used in etcd, Patroni, and HAProxy configuration. |
