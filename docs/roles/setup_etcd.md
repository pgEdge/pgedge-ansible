# setup_etcd

## Overview

The `setup_etcd` role configures and starts etcd as a distributed consensus cluster for high availability PostgreSQL deployments. It creates the etcd configuration file with cluster membership and starts the etcd service on all nodes in a zone.

## Purpose

The role performs the following tasks:

- generates the etcd cluster configuration file.
- configures cluster membership for all nodes in each zone.
- sets appropriate network endpoints and URLs.
- enables and starts etcd service.
- establishes distributed key-value store for Patroni.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `install_etcd`: You must install etcd binaries and service

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
    This role is only required for high availability deployments when you enable the `is_ha_cluster` parameter. Standalone PostgreSQL instances do not need etcd.

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

This role is idempotent and safe to re-run. Subsequent executions will:

- not overwrite an existing cluster.
- Regenerate configuration files each run to incorporate changes.
- leave Etcd in an enabled and running state.

!!! warning "Configuration Changes"
    Changing etcd cluster membership after initial setup requires special procedures. Adding or removing nodes should be done using etcdctl, not by re-running this role.

## Notes

You can monitor etcd cluster health:

```bash
# Check cluster health
/usr/local/etcd/etcdctl endpoint health

# Check cluster status
/usr/local/etcd/etcdctl endpoint status --write-out=table

# List cluster members
/usr/local/etcd/etcdctl member list
```
