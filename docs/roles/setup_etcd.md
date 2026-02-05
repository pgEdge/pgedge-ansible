# setup_etcd

The `setup_etcd` role configures and starts etcd as a distributed consensus
cluster for high availability Postgres deployments. The role creates the etcd
configuration file with cluster membership and starts the etcd service on all
nodes in a zone.

The role performs the following tasks on inventory hosts:

- Generate the etcd cluster configuration file with node membership.
- Configure cluster membership for all nodes within each zone.
- Set appropriate network endpoints and peer URLs.
- Enable and start the etcd service for cluster formation.
- Establish a distributed key-value store for Patroni coordination.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_etcd` installs etcd binaries and the systemd service file.

## When to Use

Execute this role on pgedge hosts in high availability configurations after
installing etcd.

In the following example, the playbook invokes the role after installing etcd:

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
    Only high availability deployments require this role when you enable the
    `is_ha_cluster` parameter; standalone Postgres instances do not need etcd.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    etcd_data_dir: /var/lib/etcd
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `etcd_user` | System user that owns the etcd process. |
| `etcd_group` | System group for etcd file ownership. |
| `etcd_install_dir` | Directory containing etcd binaries. |
| `etcd_config_dir` | Directory for etcd configuration files. |
| `etcd_data_dir` | Directory for etcd cluster data storage. |

## How It Works

The role configures etcd for distributed consensus within each zone.

### Cluster Setup

When the role runs on pgedge hosts, it performs these steps:

1. Check for existing cluster configuration.
    - Look for the `{{ etcd_data_dir }}/postgresql` directory.
    - Skip setup when the cluster is already configured.

2. Create the configuration directory.
    - Create `etcd_config_dir` directory with proper ownership.
    - Set ownership to `etcd:etcd` for the service user.

3. Generate the cluster configuration file.
    - Create `{{ etcd_config_dir }}/etcd.yaml` with cluster settings.
    - Configure node identity with hostname and advertise URLs.
    - Set initial cluster membership for all nodes in the zone.
    - Configure network endpoints for client and peer communication.
    - Set the data directory to `{{ etcd_data_dir }}/postgresql`.

4. Start the etcd service.
    - Enable the etcd service for automatic startup.
    - Start the etcd service to begin cluster formation.

!!! info "Zone Isolation"
    Each zone maintains its own independent etcd cluster for Patroni
    coordination within that zone.

!!! important "Cluster Formation"
    Start all nodes in the etcd cluster within a reasonable time window to
    form quorum; if you start nodes too far apart, cluster formation may fail.

### Configuration Details

The generated configuration file includes the following settings.

**Node Identity:**

- `name` contains the node hostname.
- `advertise-client-urls` specifies the HTTP URL for client connections.
- `initial-advertise-peer-urls` specifies the HTTP URL for peer communication.

**Cluster Membership:**

- `initial-cluster` lists all nodes in the zone with peer URLs.
- `initial-cluster-state` uses the value `new` for initial bootstrap.
- `initial-cluster-token` identifies the cluster as `pgedge_cluster`.

**Network Configuration:**

- `listen-client-urls` listens on the node IP and localhost on port 2379.
- `listen-peer-urls` listens on the node IP for peer communication on port
  2380.

**Timeouts:**

- `dial-timeout` uses a value of 20 seconds.
- `read-timeout` uses a value of 20 seconds.
- `write-timeout` uses a value of 20 seconds.

!!! warning "Initial State"
    The role uses `new` as the initial cluster state to establish node
    consensus; new etcd nodes cannot join after the bootstrap phase, so
    operators must add new nodes manually with `etcdctl`.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic etcd Cluster

In the following example, the playbook deploys an etcd cluster for HA:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - setup_etcd
  when: is_ha_cluster
```

### Full HA Deployment

In the following example, the playbook deploys a complete HA cluster with
etcd, Patroni, and Postgres:

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

In the following example, the inventory file defines zone assignments for
multi-zone deployment:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
  hosts:
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
```

The role configures etcd nodes within the proper zone automatically; each zone
has its own independent etcd cluster.

### Custom Data Directory

In the following example, the playbook specifies a custom data directory:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_data_dir: /data/etcd
  roles:
    - install_etcd
    - setup_etcd
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/etcd/etcd.yaml` | New | Main etcd configuration file with cluster membership and network settings. |
| `{{ etcd_data_dir }}/postgresql/` | New | Cluster data directory containing member data and WAL logs. |

## Platform-Specific Behavior

This role is platform-agnostic because it installs etcd binaries directly
from GitHub releases; the role works identically on any systemd-based Linux
distribution.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Skip cluster setup when the data directory already contains cluster data.

The role may update these items on subsequent runs:

- Regenerate configuration files to incorporate inventory changes.
- Start and enable the etcd service within Systemd.

!!! warning "Configuration Changes"
    Changing etcd cluster membership after initial setup requires special
    procedures; use `etcdctl` to add or remove nodes rather than re-running
    this role.

!!! warning "Data Directory"
    The etcd data directory contains critical cluster state; back up this
    directory before making cluster changes because loss of quorum makes the
    cluster unavailable.
