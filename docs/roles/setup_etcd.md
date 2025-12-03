# setup_etcd

## Overview

The `setup_etcd` role configures and starts etcd as a distributed consensus cluster for high availability PostgreSQL deployments. It creates the etcd configuration file with cluster membership and starts the etcd service on all nodes in a zone.

## Purpose

- Generate etcd cluster configuration file
- Configure cluster membership for all nodes in each zone
- Set appropriate network endpoints and URLs
- Enable and start etcd service
- Establish distributed key-value store for Patroni

## Role Dependencies

- `role_config` - Provides shared configuration variables
- `install_etcd` - etcd binaries and service must be installed

## When to Use

Execute this role on **pgedge hosts** in high availability configurations after installing etcd:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - setup_etcd
  when: is_ha_cluster
```

!!! important "HA Clusters Only"
    This role is only required for high availability deployments where `is_ha_cluster: true`. Standalone PostgreSQL instances do not need etcd.

## Parameters

This role uses the following configuration parameters:

* `etcd_user`
* `etcd_group`
* `etcd_install_dir`
* `etcd_config_dir`
* `etcd_data_dir`

## Tasks Performed

### 1. Configuration Check

- Checks if etcd data directory for PostgreSQL cluster exists
- Looks for `{{ etcd_data_dir }}/postgresql` directory
- Skips setup if cluster is already configured

### 2. Configuration Directory Creation

- Creates `etcd_config_dir` directory
- Sets ownership to `etcd:etcd`
- Ensures proper permissions for configuration files

### 3. Cluster Configuration File Generation

Creates `{{ etcd_config_dir }}/etcd.yaml` with:

**Node Identity:**

- `name`: Node's hostname
- `advertise-client-urls`: HTTP URL for client connections (port 2379)
- `initial-advertise-peer-urls`: HTTP URL for peer communication (port 2380)

**Cluster Membership:**

- `initial-cluster`: List of all nodes in zone with peer URLs
- Format: `hostname1=http://host1:2380,name2=http://host2:2380,...`
- Automatically includes all nodes from `nodes_in_zone` variable

!!! info "Zone Isolation"
    etcd clusters are isolated per zone. Each zone has its own independent etcd cluster for Patroni coordination within that zone.

**Cluster State:**

- `initial-cluster-state`: Set to `new` for initial bootstrap
- `initial-cluster-token`: `pgedge_cluster` for cluster identification

!!! warning "Initial State"
    The role uses `new` as the initial cluster state to establish node consensus. This role cannot (yet) add new etcd nodes after this bootstrap phase, so new nodes must be added manually with `etcdctl`.

**Network Configuration:**

- `listen-client-urls`: Listens on node IP and localhost (port 2379)
- `listen-peer-urls`: Listens on node IP for peer communication (port 2380)

**Data Storage:**

- `data-dir`: `{{ etcd_data_dir }}/postgresql` for cluster data

!!! warning "Data Directory"
    The etcd data directory contains critical cluster state. Back up this directory before making cluster changes. Loss of quorum (majority of nodes) will make the cluster unavailable.

**Timeouts:**

- `dial-timeout`: 20 seconds
- `read-timeout`: 20 seconds
- `write-timeout`: 20 seconds

### 4. Service Startup

- Enables etcd service for automatic startup
- Starts etcd service
- Service begins cluster formation with other nodes

!!! important "Cluster Formation"
    All nodes in the etcd cluster must be started within a reasonable time window to form quorum. If nodes are started too far apart, cluster formation may fail.

## Files Generated

### Configuration Files

- `/etc/etcd/etcd.yaml` - Main etcd configuration file (mode `644`, owner: `etcd:etcd`)

### Data Files

- `{{ etcd_data_dir }}/postgresql/` - Cluster data directory
- `{{ etcd_data_dir }}/postgresql/member/` - Member data and WAL logs

### Log Files

etcd logs to systemd journal. View with:

```bash
sudo journalctl -u etcd -f
```

## Platform-Specific Behavior

### All Supported Platforms

This role is platform-agnostic as it installs pre-compiled binaries directly from GitHub. It should work identically on any systemd-based Linux distribution.

## Example Usage

### Basic etcd Cluster Setup

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - setup_etcd
  when: is_ha_cluster
```

### HA Deployment

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
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

### Multi-Zone Deployment

To use multiple zones, ensure the inventory file includes zone assignment:

```yaml
# Inventory File
pgedge:
  vars:
    is_ha_cluster: true
  host1:
    zone: 1
  host2:
    zone: 1
  host3:
    zone: 1
  host4:
    zone: 2
  host5:
    zone: 2
  host6:
    zone: 2
...
```

Then the role will configure etcd nodes within the proper zone automatically.

```yaml
# Playbook
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_etcd
```

Each zone will have its own independent etcd cluster.

### Custom Data Directory

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_data_dir: "/data/etcd"
  roles:
    - install_etcd
    - setup_etcd
```

## Idempotency

This role is designed for idempotency:

- Checks for existing cluster data before configuration
- Skips setup if `{{ etcd_data_dir }}/postgresql` exists
- Configuration file updates are safe but may require service restart
- Service enable/start operations are idempotent

!!! warning "Configuration Changes"
    Changing etcd cluster membership after initial setup requires special procedures. Adding or removing nodes should be done using etcdctl, not by re-running this role.

## Troubleshooting

### Service Fails to Start

**Symptom:** etcd service won't start

**Solution:**

- Check etcd logs:

```bash
sudo journalctl -u etcd -n 50 --no-pager
```

- Check for port conflicts:

```bash
sudo netstat -tlnp | grep -E '2379|2380'
```

### Cluster Formation Fails

**Symptom:** etcd nodes can't form cluster

**Solution:**

- Verify all nodes are listed in initial-cluster
- Check network connectivity between nodes:

```bash
curl http://other-node:2379/health
```

- Ensure firewall allows etcd ports (2379, 2380):

```bash
# RHEL
sudo firewall-cmd --add-port=2379/tcp --permanent
sudo firewall-cmd --add-port=2380/tcp --permanent
sudo firewall-cmd --reload

# Debian
sudo ufw allow 2379/tcp
sudo ufw allow 2380/tcp
```

- Verify hostnames resolve correctly:

```bash
ping hostname1
ping hostname2
```

### "cluster ID mismatch" Error

**Symptom:** etcd fails with cluster ID mismatch

**Solution:**

- This occurs when data directories have conflicting cluster state
- Remove existing data and reconfigure:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

- Ensure all nodes start fresh or all have consistent state

### "member already exists" Error

**Symptom:** Node fails to join with "member already exists"

**Solution:**

- Check existing cluster members:

```bash
/usr/local/etcd/etcdctl member list
```

- Remove the old member:

```bash
/usr/local/etcd/etcdctl member remove <member-id>
```

- Clear data directory and restart:

```bash
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd/postgresql
sudo systemctl start etcd
```

### Slow Performance or Timeouts

**Symptom:** etcd operations are slow or timing out

**Solution:**

- Manually compact the cluster history and defrag storage:

```bash
/usr/local/etcd/etcdctl compact 5
/usr/local/etcd/etcdctl defrag
```

- Check network latency between nodes:

```bash
ping -c 10 other-node
```

- Verify disk I/O performance (etcd is disk-sensitive):

```bash
sudo iostat -dmx
```

- Consider using SSD for etcd data directory
- Increase timeout values in configuration:

```yaml
dial-timeout: 30s
read-timeout: 30s
write-timeout: 30s
```

### Cannot Connect to Cluster

**Symptom:** etcdctl commands fail to connect

**Solution:**

- Verify etcd is running:

```bash
sudo systemctl status etcd
```

- Check listening addresses:

```bash
sudo netstat -tlnp | grep etcd
```

- Test local connection:

```bash
curl http://127.0.0.1:2379/health
```

## Notes

Monitor etcd cluster health:

```bash
# Check cluster health
/usr/local/etcd/etcdctl endpoint health

# Check cluster status
/usr/local/etcd/etcdctl endpoint status --write-out=table

# List cluster members
/usr/local/etcd/etcdctl member list
```

## See Also

- [Configuration Reference](../configuration.md) - etcd configuration variables
- [Architecture](../architecture.md) - Understanding HA cluster topology and zones
- [install_etcd](install_etcd.md) - Required prerequisite for etcd binaries
- [setup_patroni](setup_patroni.md) - Configures Patroni to use etcd cluster
