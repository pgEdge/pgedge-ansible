# setup_etcd

The `setup_etcd` role configures and starts etcd as a distributed consensus
cluster for high availability Postgres deployments. The role creates the etcd
configuration file with cluster membership and starts the etcd service on all
nodes in a zone.

The role performs the following tasks on inventory hosts:

- Generate TLS certificates for etcd peer and client communication on nodes
  that do not yet have etcd data.
- Generate the etcd configuration file listing all zone nodes as cluster peers.
- Restart existing members one at a time when their configuration changes.
- Start the etcd systemd service.

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
| `etcd_auto_compaction_mode` | Whether the compaction retention is a duration or a revision count. |
| `etcd_auto_compaction_retention` | Key history etcd keeps before compacting it. |
| `etcd_quota_backend_bytes` | Database size at which etcd stops accepting writes. |

See the [Configuration Reference](../configuration.md) for defaults.

## How It Works

The role configures etcd for distributed consensus within each zone.

1. Check for an existing etcd data directory.
2. On a node without one, generate TLS certificates: a certificate authority
   (`ca.crt`), a peer key and certificate (`peer.key`, `peer.crt`), and a
   server key and certificate (`server.key`, `server.crt`). A node with etcd
   data keeps the certificates it has.
3. Generate the etcd configuration file at `{{ etcd_config_dir }}/etcd.yaml`
   with node identity, cluster membership for all nodes in the same zone, and
   network endpoints for client (port 2379) and peer (port 2380) communication.
4. Restart each existing member whose configuration changed, one at a time.
   Before each restart the role checks that every member of the zone is
   healthy, and after it waits until they are again.
5. Start and enable the etcd service.

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

Keyspace maintenance uses these values:

- `auto-compaction-mode` and `auto-compaction-retention` compact key history
  older than one hour by default.
- `quota-backend-bytes` sets the database size at which etcd stops accepting
  writes, 2 GiB by default.

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

This role renders the etcd configuration on every run, so a changed parameter
reaches a running cluster with the next deployment. etcd reads its
configuration only at startup and cannot reload it, so the role restarts each
member whose file changed. It restarts them one at a time, so the zone keeps
its quorum and Patroni keeps its leader lock. A run that changes nothing
restarts nothing.

The bootstrap settings in the file (`initial-cluster`, `initial-cluster-state`
and `initial-cluster-token`) are read only when a member starts with an empty
data directory, so re-rendering them on an existing member has no effect.

Certificates are issued only to a node without etcd data. An existing member
keeps the certificates it was built with.

!!! warning "Degraded zones"
    The role refuses to restart a member while any member of its zone is
    unhealthy, because taking a second member down can cost the zone its
    quorum. The new configuration is still written and takes effect when etcd
    next starts. Restore the zone to health and run the deployment again.

!!! warning "Configuration Changes"
    Changing etcd cluster membership after initial setup requires special
    procedures. Use `etcdctl` to add or remove nodes rather than re-running
    this role.

!!! warning "Data Directory"
    The etcd data directory contains critical cluster state. Back up this
    directory before making cluster changes because loss of quorum makes the
    cluster unavailable.
