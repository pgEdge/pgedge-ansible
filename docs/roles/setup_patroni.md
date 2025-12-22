# setup_patroni

## Overview

The `setup_patroni` role configures and starts Patroni for high availability PostgreSQL cluster management. It creates the Patroni configuration file with etcd connection details, PostgreSQL settings, and cluster policies, then orchestrates the startup sequence to ensure proper cluster formation.

## Purpose

This role performs the following tasks:

- Generates Patroni configuration file with cluster settings.
- Configures etcd connection for distributed consensus.
- Sets up PostgreSQL parameters managed by Patroni.
- Configures authentication for replication and superuser access.
- Manages `pg_hba.conf` rules through Patroni.
- Disables native PostgreSQL service in favor of Patroni.
- Orchestrates primary-first startup sequence.
- Establishes a highly availabile cluster.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `install_patroni`: You must install Patroni binaries
- `setup_etcd`: The etcd cluster must be running
- `setup_postgres`: You must initialize PostgreSQL

## When to Use

Execute this role on **all pgedge hosts** in high availability configurations after setting up etcd and PostgreSQL:

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
    This role is only required for high availability deployments when you enable the `is_ha_cluster` parameter. Standalone PostgreSQL instances do not use Patroni.

## Parameters

This role uses the following configuration parameters:

### Database Configuration

* `db_list`
* `pg_port`
* `pg_data`
* `pg_path`
* `pg_home`
* `pg_service_name` - Primarily used to replace Postgres with Patroni service management

### Users and Authentication

* `backup_user`
* `db_user`
* `db_password`
* `pgedge_user`
* `replication_user`
* `replication_password`

### Patroni Settings

* `patroni_bin_dir`
* `patroni_config_dir`

### Extension and Replication

* `spock_exception_behaviour`
* `synchronous_mode`
* `synchronous_mode_strict`

## Tasks Performed

### 1. Patroni Configuration File Generation

Creates `{{ patroni_config_dir }}/patroni.yaml` with comprehensive settings:

**Cluster Identification:**

- `scope`: `pgedge` - Cluster name in etcd
- `namespace`: `/db/` - etcd key prefix
- `name`: Node hostname
- `replication_slot_name`: Sanitized hostname for replication slot

**REST API Configuration:**

- Listens on all interfaces port 8008
- Used for health checks and cluster management
- Connect address uses inventory hostname

**etcd Connection:**

- Host: `{{ inventory_hostname }}:2379`
- TTL: 30 seconds
- Protocol: HTTP (unencrypted)

**Bootstrap DCS Settings:**

- `ttl`: 30 seconds - Leader key TTL in etcd
- `loop_wait`: 10 seconds - Time between checks
- `retry_timeout`: 10 seconds - Retry interval for failed operations
- `maximum_lag_on_failover`: 1MB - Max acceptable lag for failover candidates
- `synchronous_mode`: Configured value
- `synchronous_mode_strict`: Configured value
- `use_pg_rewind`: true - Use pg_rewind for diverged replicas
- `use_slots`: true - Use replication slots

**PostgreSQL Parameters:**

Managed cluster-wide by Patroni:

- Port, SSL certificates, listen addresses
- Archive mode and command
- WAL level (logical for Spock)
- Worker processes and replication slots
- Spock configuration (DDL replication, conflict resolution, exception handling)
- Snowflake zone setting

!!! info "Configuration Management"
    Patroni manages most PostgreSQL configuration. Direct edits to `postgresql.conf` may be overwritten. Use the `patronictl` utility for cluster-wide settings.

**Spock Slot Ignore:**

- Ignores logical replication slots created by Spock
- Prevents Patroni from interfering with Spock replication

**PostgreSQL Connection Details:**

- Listen address and port
- Connect address for cluster communication
- Config, data, and bin directories
- `.patroni_pgpass` location for password storage

**pg_hba.conf Management:**

Patroni manages pg_hba.conf with rules for:

- Local postgres peer access
- Localhost connections
- pgEdge user communication between all pgedge nodes
- Admin user access from all pgedge nodes
- Replication user access within zone
- Proxy server access (if configured)
- Backup server access (if configured)
- Custom HBA rules

!!! warning "pg_hba.conf"
    Patroni manages `pg_hba.conf`. Manual changes will be overwritten. Use `custom_hba_rules` or `patronictl` instead.

**Authentication:**

- Replication user credentials for streaming replication
- Superuser credentials for cluster management

### 2. PostgreSQL Service Disable

- Disables native PostgreSQL systemd service
- Ensures Patroni has exclusive control of PostgreSQL lifecycle
- Prevents conflicts between Patroni and systemd management

### 3. Orchestrated Service Startup

**Primary Node First:**

- Starts Patroni on `first_node_in_zone` immediately
- Primary establishes cluster scope and initializes etcd keys
- Becomes cluster leader

**Replica Nodes Wait:**

- Replica nodes wait for primary to establish cluster
- Checks for primary availability before starting
- Prevents race conditions in cluster formation

**Replica Node Startup:**

- Starts Patroni service after primary is ready
- Patroni automatically bootstraps from primary
- Joins cluster as replica

### 4. Configuration Restart

- Restarts PostgreSQL through Patroni to apply configuration changes
- Uses `patronictl restart` to clear "Pending restart" flag
- Ensures all settings take effect
- Performed on all nodes

## Files Generated

### Configuration Files

- `/etc/patroni/patroni.yaml` - Main Patroni configuration (mode 600, owner: postgres)
- `{{ pg_home }}/.patroni_pgpass` - Password file for Patroni (mode 600, owner: postgres)

### etcd Keys

Patroni creates keys in etcd under `/db/pgedge/`:

- `/db/pgedge/leader` - Current cluster leader
- `/db/pgedge/members/<hostname>` - Member metadata
- `/db/pgedge/config` - Cluster configuration
- `/db/pgedge/initialize` - Initialization key

## Platform-Specific Behavior

### All Supported Platforms

This role behaves identically on:

- Debian 12
- Rocky Linux 9

Platform differences are handled through variables:

- `pg_service_name` - OS-specific service name
- `pg_path`, `pg_config_dir`, `pg_data` - OS-specific paths

## Example Usage

### Basic HA Cluster Setup

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

### Multi-Node Cluster with Custom HBA Rules

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

## Idempotency

This role has limited idempotency:

- Regenerates configuration files each run to incorporate changes.
- Only modifies services which aren't already in their intended state.
- Always restarts Patroni and/or Postgres to ensure configuration changes apply.

!!! warning "Configuration Updates"
    Changes to Patroni configuration require service restart. The role performs this automatically via patronictl.

## Troubleshooting

### Patroni Service Fails to Start

**Symptom:** Patroni service won't start

**Solution:**

- Check Patroni logs:

```bash
sudo journalctl -u patroni -n 50 -f
```

- Verify configuration syntax:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patroni --validate-config /etc/patroni/patroni.yaml
```

- Check etcd connectivity:

```bash
curl http://localhost:2379/health
```

### etcd Connection Fails

**Symptom:** Patroni can't connect to etcd

**Solution:**

- Verify etcd is running:

```bash
sudo systemctl status etcd
```

- Test etcd connectivity:

```bash
curl http://localhost:2379/v3/cluster/member/list
```

- Check firewall allows port 2379
- Verify etcd hostname resolution

### Cluster Formation Fails

**Symptom:** Patroni starts but cluster doesn't form

**Solution:**

- Check etcd keys:

```bash
/usr/local/etcd/etcdctl get --prefix /db/pgedge/
```

- Verify all nodes see each other in etcd
- Check for split-brain scenarios
- Review Patroni logs on all nodes
- Ensure primary started first

### "Pending Restart" Status Persists

**Symptom:** Patroni shows "Pending restart" after configuration changes

**Solution:**

- Restart using patronictl:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge <hostname>
```

- Or restart all nodes:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml restart pgedge
```

### Replication Not Working

**Symptom:** Replicas not streaming from primary

**Solution:**

- Check Patroni cluster status:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml list
```

- Verify replication user credentials
- Check pg_hba.conf allows replication connections
- Verify network connectivity between nodes
- Check PostgreSQL logs for replication errors

### Synchronous Replication Blocks Writes

**Symptom:** Writes hang when synchronous_mode_strict is enabled

**Solution:**

- Check replica status:

```bash
sudo -u postgres psql -c "SELECT * FROM pg_stat_replication;"
```

- Verify at least one synchronous replica is available
- Temporarily disable strict mode if needed:

```bash
sudo -u postgres /var/lib/pgsql/.local/bin/patronictl -c /etc/patroni/patroni.yaml edit-config
```

### REST API Not Accessible

**Symptom:** Cannot access Patroni REST API on port 8008

**Solution:**

- Verify Patroni is listening:

```bash
sudo netstat -tlnp | grep 8008
```

- Check firewall rules:

```bash
# RHEL
sudo firewall-cmd --list-all

# Debian
sudo ufw status
```

- Test local access:

```bash
curl http://localhost:8008/
```

### PostgreSQL Still Managed by systemd

**Symptom:** PostgreSQL service starts independently of Patroni

**Solution:**

- Verify PostgreSQL service is disabled:

```bash
sudo systemctl is-enabled postgresql  # or postgresql-17
```

- Manually disable:

```bash
sudo systemctl disable postgresql
sudo systemctl stop postgresql
```

- Restart Patroni:

```bash
sudo systemctl restart patroni
```

## Notes

You can use `patronictl` for cluster operations:

```bash
# List cluster status
patronictl -c /etc/patroni/patroni.yaml list

# Switchover to a new primary
patronictl -c /etc/patroni/patroni.yaml switchover

# Reinitialize a replica
patronictl -c /etc/patroni/patroni.yaml reinit pgedge <hostname>
```

## See Also

- [Configuration Reference](../configuration.md) - Patroni configuration variables
- [Architecture](../architecture.md) - Understanding HA cluster topology
- [install_patroni](install_patroni.md) - Required prerequisite for Patroni binaries
- [setup_etcd](setup_etcd.md) - Required prerequisite for etcd cluster
- [setup_postgres](setup_postgres.md) - PostgreSQL initialization before Patroni
- [setup_haproxy](setup_haproxy.md) - HAProxy uses Patroni REST API for health checks
