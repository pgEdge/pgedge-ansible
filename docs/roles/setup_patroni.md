# setup_patroni

The `setup_patroni` role configures and starts Patroni for high availability
Postgres cluster management. The role generates the Patroni configuration file
with etcd connection details and Postgres settings, then orchestrates the
startup sequence to ensure proper cluster formation.

The role performs the following tasks on inventory hosts:

- Generate TLS certificates for Patroni REST API communication.
- Generate the `patroni.yaml` configuration file from a template.
- Disable the native Postgres systemd service so Patroni takes control.
- Start Patroni on the primary node first, then on all replica nodes.
- Wait for the cluster to reach a running state before proceeding.
- Apply a `patronictl restart` to clear any "Pending Restart" flag.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_patroni` installs Patroni packages and creates the config directory.
- `setup_etcd` starts the etcd cluster for distributed consensus.
- `setup_postgres` initializes Postgres instances.

## When to Use

Execute this role on all pgedge hosts in high availability configurations
after setting up etcd and Postgres.

In the following example, the playbook invokes the role after etcd and
Postgres setup:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - setup_etcd
    - setup_patroni
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `custom_hba_rules` | Additional rules applied to `pg_hba.conf` on all nodes. |
| `db_names` | Databases to configure for the cluster. |
| `pg_port` | Postgres port for client connections. |
| `pg_data` | Postgres data directory path. |
| `pg_path` | Postgres binary directory path. |
| `pg_home` | Home directory for the postgres OS user. |
| `backup_user` | Backup user for pg_hba.conf rules. |
| `db_user` | Admin database user. |
| `db_password` | Password for the admin database user. |
| `pgedge_user` | pgEdge user for node-to-node Spock connections. |
| `replication_user` | User for Patroni streaming replication. |
| `replication_password` | Password for the replication user. |
| `patroni_tls_dir` | Directory for Patroni TLS certificate files. |
| `synchronous_mode` | Enable synchronous replication mode. |
| `synchronous_mode_strict` | Require a synchronous replica for all commits. |
| `tls_validity_days` | Number of days TLS certificates remain valid. |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

The role configures Patroni and orchestrates cluster formation.

### Patroni Configuration

The role performs the following steps:

1. Copy the CA certificate from `{{ etcd_tls_dir }}` and generate a Patroni
   client key and certificate for communicating with etcd.
2. Generate the Patroni configuration file. On RHEL systems the file is named
   `patroni.yml`; on Debian systems the file is named
   `{{ pg_version }}-{{ cluster_name }}.yml`. Both files are stored in
   `/etc/patroni/`.
3. Disable the native Postgres systemd service so Patroni has exclusive control
   of the Postgres lifecycle.
4. Start Patroni on the designated primary node and wait for the cluster
   primary to become available.
5. Start Patroni on all replica nodes. Patroni rebuilds each replica from the
   primary using streaming replication.
6. Wait for the cluster to reach a running state (up to 30 retries with a
   10-second delay between attempts).
7. Restart Postgres through Patroni to apply settings and clear the
   "Pending Restart" flag.

### Postgres Settings Managed by Patroni

Patroni configures PostgreSQL with the following settings for Spock
compatibility:

- WAL level set to `logical`.
- Shared preload libraries set to `pg_stat_statements`, `snowflake`, and
  `spock`.
- DDL replication enabled via Spock.
- Spock replication slots excluded from Patroni slot management to prevent
  conflicts.

!!! info "Configuration Management"
    Patroni manages most Postgres configuration and may overwrite direct edits
    to `postgresql.conf`. Use `patronictl` for cluster-wide setting changes.

!!! warning "pg_hba.conf"
    Patroni manages `pg_hba.conf` and will overwrite manual changes. Use
    `custom_hba_rules` in the inventory to add custom authentication rules.

## Usage Examples

In the following example, the playbook deploys an HA cluster with synchronous
replication enabled:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    synchronous_mode_strict: true
  roles:
    - setup_patroni
```

In the following example, the playbook adds custom `pg_hba.conf` rules through
the Patroni configuration:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    custom_hba_rules:
      - contype: hostssl
        users: app_user
        databases: production
        source: 10.0.0.0/8
        method: scram-sha-256
  roles:
    - setup_patroni
```

## Artifacts

This role generates the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/patroni/patroni.yml` (RHEL) | New | Patroni configuration file with cluster settings and Postgres parameters. |
| `/etc/patroni/{{ pg_version }}-{{ cluster_name }}.yml` (Debian) | New | Patroni configuration file on Debian systems. |
| `{{ patroni_tls_dir }}/ca.crt` | New | Certificate authority for validating etcd server certificates. |
| `{{ patroni_tls_dir }}/patroni.key` | New | Private key for encrypting traffic to etcd. |
| `{{ patroni_tls_dir }}/patroni.crt` | New | Certificate for communicating with etcd as a client. |
| `{{ pg_home }}/.patroni_pgpass` | New | Password file for Patroni database connections with mode 600. |

## Platform-Specific Behavior

On Debian-based systems, the configuration file is named
`{{ pg_version }}-{{ cluster_name }}.yml`. For example, the default settings
produce a file named `/etc/patroni/17-demo.yml`. On RHEL-based systems, the
configuration file is named `patroni.yml`.

## Idempotency

This role has limited idempotency. The role regenerates configuration files,
disables the native Postgres service, and restarts Patroni and Postgres on
subsequent runs to ensure configuration changes apply.

!!! warning "Configuration Updates"
    Changes to Patroni configuration require a service restart. The role
    performs this automatically via `patronictl restart`.
