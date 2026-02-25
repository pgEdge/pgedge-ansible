# setup_patroni

The `setup_patroni` role configures and starts Patroni for high availability
Postgres cluster management. The role creates the Patroni configuration file
with etcd connection details, Postgres settings, and cluster policies, then
orchestrates the startup sequence to ensure proper cluster formation.

The role performs the following tasks on inventory hosts:

- Produce TLS certificates for secure communication.
- Generate the Patroni configuration file with cluster settings.
- Configure etcd connection for distributed consensus.
- Set up Postgres parameters managed by Patroni.
- Configure authentication for replication and superuser access.
- Manage `pg_hba.conf` rules through Patroni configuration.
- Disable the native Postgres service in favor of Patroni management.
- Orchestrate the primary-first startup sequence for cluster formation.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_patroni` installs Patroni binaries and dependencies.
- `setup_etcd` starts the etcd cluster for distributed consensus.
- `setup_postgres` initializes and configures Postgres instances.

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
  when: is_ha_cluster
```

!!! note "HA Clusters Only"
    Only high availability deployments require this role when you enable the
    `is_ha_cluster` parameter; standalone Postgres instances do not use
    Patroni.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    synchronous_mode: true
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `custom_hba_rules` | Additional rules applied to `pg_hba.conf` on all nodes. |
| `db_names` | Databases to configure for the cluster. |
| `pg_port` | Postgres port for client connections. |
| `pg_data` | Postgres data directory path. |
| `pg_path` | Postgres binary directory path. |
| `pg_home` | Home directory for the postgres user. |
| `pg_service_name` | Native Postgres service name to disable. |
| `backup_user` | Backup user for pg_hba.conf rules. |
| `db_user` | Admin database user. |
| `db_password` | Password for the admin database user. |
| `pgedge_user` | pgEdge user for node communication. |
| `replication_user` | User for Patroni streaming replication. |
| `replication_password` | Password for the replication user. |
| `patroni_tls_dir` | Set the directory for Patroni TLS certificate files. |
| `spock_exception_behaviour` | Spock replication exception handling behavior. |
| `synchronous_mode` | Enable synchronous replication mode. |
| `synchronous_mode_strict` | Require synchronous replica for commits. |
| `tls_validity_days` | The number of days TLS certificates remain valid. |

## How It Works

The role configures Patroni and orchestrates cluster formation.

### Patroni Configuration

This role performs the following steps on target pgedge hosts:

1. Produce TLS certificates for secure communication.
    - Copies CA certificate (`ca.crt`) from `{{ etcd_tls_dir }}`.
    - Creates a new client key named `patroni.key`.
    - Uses the `patroni.key` key to generate a `patroni.crt` certificate.

2. Generate the Patroni configuration file.
    - Create a configuration file in `/etc/patroni` with cluster settings.
      - RHEL systems use `patroni.yml`.
      - Debian systems use `{{ pg_version }}-{{ cluster_name }}.yml`.
    - Configure cluster identification with scope, namespace, and node name.
    - Set REST API endpoints for health checks and management.
    - Configure etcd connection details for distributed consensus.
    - Set bootstrap DCS settings for cluster policies.
    - Configure Postgres parameters managed by Patroni.
    - Set up `pg_hba.conf` rules for authentication.
    - Configure replication and superuser credentials.

3. Disable the native Postgres service.
    - Disable the systemd Postgres service.
    - Ensure Patroni has exclusive control of the Postgres lifecycle.

4. Start the Patroni service on the primary node.
    - Start Patroni on the designated bootstrap primary node immediately.
    - Establish the cluster scope and initialize etcd keys.
    - The primary node becomes the cluster leader.

5. Start the Patroni service on replica nodes.
    - Wait for the primary to establish the cluster.
    - Check for primary availability before starting.
    - Start Patroni to bootstrap from the primary.
    - Join the cluster as a replica.

6. Apply configuration changes.
    - Restart Postgres through Patroni to apply settings.
    - Use `patronictl restart` to clear the "Pending restart" flag.

!!! info "Configuration Management"
    Patroni manages most Postgres configuration and may overwrite direct edits
    to `postgresql.conf`, so use the `patronictl` utility for cluster-wide
    settings.

### Configuration Details

The generated configuration file includes the following settings.

**Cluster Identification:**

- `scope` contains `pgedge` as the cluster name in etcd.
- `namespace` contains `/db/` as the etcd key prefix.
- `name` contains the node hostname.

**REST API Configuration:**

- Listens on all interfaces on port 8008.
- Patroni uses this endpoint for health checks and cluster management.

**etcd Connection:**

- Host uses `{{ inventory_hostname }}:2379`.
- TTL uses a value of 30 seconds.

**Bootstrap DCS Settings:**

- `ttl` uses 30 seconds for leader key TTL in etcd.
- `loop_wait` uses 10 seconds between checks.
- `retry_timeout` uses 10 seconds for failed operations.
- `maximum_lag_on_failover` uses 1MB for failover candidates.
- `use_pg_rewind` enables recovery for diverged replicas.
- `use_slots` enables replication slots.

**Postgres Parameters:**

Patroni manages these parameters cluster-wide:

- Port, SSL certificates, and listen addresses.
- Archive mode and archive command.
- WAL level uses `logical` for Spock.
- Worker processes and replication slots.
- Spock configuration for DDL replication and conflict resolution.
- Snowflake zone setting.

**pg_hba.conf Management:**

Patroni manages `pg_hba.conf` with rules for:

- Local postgres peer access.
- Localhost connections.
- pgEdge user communication between all pgedge nodes.
- Admin user access from all pgedge nodes.
- Replication user access within the zone.
- Proxy server access when configured.
- Backup server access when configured.
- Custom HBA rules from inventory.

!!! warning `pg_hba.conf`
    Patroni manages `pg_hba.conf` and will overwrite manual changes, so use
    `custom_hba_rules` or `patronictl` instead.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic HA Cluster

In the following example, the playbook deploys a basic HA cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
  roles:
    - setup_postgres
    - setup_etcd
    - setup_patroni
```

### Synchronous Replication Cluster

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

### Custom HBA Rules

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

### Full HA Deployment

In the following example, the playbook deploys a complete HA cluster with all
required components:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    db_names:
      - production
      - staging
    zone: 1
  roles:
    - init_server
    - install_repos
    - install_pgedge
    - install_etcd
    - install_patroni
    - setup_postgres
    - setup_etcd
    - setup_patroni
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/patroni/[NAME].yml` | New | Main Patroni configuration file with cluster settings, etcd connection, and Postgres parameters. NAME is `patroni` on RHEL systems and `{{ pg_version }}-{{ cluster_name }}` on Debian systems. |
| `/etc/patroni/tls/ca.crt` | New | Certificate authority file used to validate etcd server certificates. |
| `/etc/patroni/tls/patroni.key` | New | Private key necessary to encrypt traffic to etcd. |
| `/etc/patroni/tls/patroni.crt` | New | Certificate for communicating with etcd as a client. |
| `{{ pg_home }}/.patroni_pgpass` | New | Password file for Patroni database connections with mode 600. |

The role also creates etcd keys under `/db/{{ pg_version }}-{{ cluster_name }}/`:

| Key | Purpose |
|-----|---------|
| `leader` | Current cluster leader. |
| `members/<hostname>` | Member metadata. |
| `config` | Cluster configuration. |
| `initialize` | Initialization key. |

## Platform-Specific Behavior

This role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, this role performs these actions:

- Names the configuration file `{{ pg_version }}-{{ cluster_name }}.yml`. For example, default settings produce a file named `/etc/patroni/17-demo.yml`.

### RHEL Family

On RHEL-based systems, this role performs these actions:

- Names the configuration file `patroni.yml`.

## Idempotency

This role has limited idempotency and may cause issues in multiple executions.

The role may update these items on subsequent runs:

- Regenerate configuration files to incorporate inventory changes.
- Disable the Postgres system service in favor of Patroni.
- Enable the Patroni system service to manage Postgres.
- Restart Patroni and Postgres to ensure configuration changes apply.

!!! warning "Configuration Updates"
    Changes to Patroni configuration require a service restart; the role
    performs this automatically via `patronictl`.
