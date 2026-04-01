# setup_etcd

The `setup_etcd` role configures and starts etcd as a distributed consensus
cluster for high availability Postgres deployments. The role creates the etcd
configuration file with cluster membership and starts the etcd service on all
nodes in a zone.

The role performs the following tasks on inventory hosts:

- Generate TLS certificates for etcd peer and client communication.
- Generate the etcd configuration file listing all zone nodes as cluster peers.
- Start the etcd systemd service if the data directory does not already exist.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_etcd` installs the etcd package and systemd service file.

## When to Use

Execute this role on pgedge hosts in high availability configurations after
installing etcd. Only high availability deployments require this role.

In the following example, the playbook invokes the role after installing etcd:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - setup_etcd
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `etcd_user` | System user that owns the etcd process. |
| `etcd_group` | System group for etcd file ownership. |
| `etcd_install_dir` | Directory containing etcd binaries. |
| `etcd_config_dir` | Directory for etcd configuration files. |
| `etcd_data_dir` | Directory for etcd cluster data storage. |
| `etcd_tls_dir` | Directory for etcd TLS certificate storage. |

See the [Configuration Reference](../configuration.md) for defaults.

## How It Works

The role configures etcd for distributed consensus within each zone.

1. Check for an existing etcd data directory. The role skips setup when the
   cluster data directory already exists.
2. Generate TLS certificates: a certificate authority (`ca.crt`), a peer
   key and certificate (`peer.key`, `peer.crt`), and a server key and
   certificate (`server.key`, `server.crt`).
3. Generate the etcd configuration file at `{{ etcd_config_dir }}/etcd.yaml`
   with node identity, cluster membership for all nodes in the same zone, and
   network endpoints for client (port 2379) and peer (port 2380) communication.
4. Start and enable the etcd service.

!!! info "Zone Isolation"
    Each zone maintains its own independent etcd cluster for Patroni
    coordination within that zone.

!!! important "Cluster Formation"
    All nodes in the etcd cluster must start within a reasonable time window.
    If nodes start too far apart, cluster formation may fail due to quorum
    requirements.

### Configuration Details

The generated configuration file includes the following settings.

Cluster identification uses these values:

- `initial-cluster-state` uses `new` for initial bootstrap.
- `initial-cluster-token` identifies the cluster as `pgedge_cluster`.

Network configuration uses these values:

- `listen-client-urls` listens on the node IP and localhost on port 2379.
- `listen-peer-urls` listens on the node IP for peer communication on port
  2380.

Timeouts are set to 20 seconds for dial, read, and write operations.

## Usage Examples

In the following example, the playbook deploys a complete HA cluster with
etcd, Patroni, and Postgres:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
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

This role generates the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ etcd_config_dir }}/etcd.yaml` | New | etcd configuration file with cluster membership and network settings. |
| `{{ etcd_tls_dir }}/ca.crt` | New | Certificate authority for validating etcd server certificates. |
| `{{ etcd_tls_dir }}/peer.key` | New | Private key for encrypting peer-to-peer etcd traffic. |
| `{{ etcd_tls_dir }}/peer.crt` | New | Certificate for etcd node-to-node communication. |
| `{{ etcd_tls_dir }}/server.key` | New | Private key for the etcd client interface. |
| `{{ etcd_tls_dir }}/server.crt` | New | Certificate for etcd client communication. |
| `{{ etcd_data_dir }}/postgresql/` | New | Cluster data directory containing member data and WAL logs. |

## Idempotency

This role skips cluster setup when the data directory already contains cluster
data. The role may regenerate configuration files to incorporate inventory
changes on subsequent runs.

!!! warning "Configuration Changes"
    Changing etcd cluster membership after initial setup requires special
    procedures. Use `etcdctl` to add or remove nodes rather than re-running
    this role.

!!! warning "Data Directory"
    The etcd data directory contains critical cluster state. Back up this
    directory before making cluster changes because loss of quorum makes the
    cluster unavailable.
