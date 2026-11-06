# setup_etcd

The `setup_etcd` role configures and starts etcd as a distributed consensus
cluster for high availability Postgres deployments. The role creates the etcd
configuration file with cluster membership and starts the etcd service on all
nodes in a zone.

The role performs the following tasks on inventory hosts:

- Generate TLS certificates for etcd peer and client communication on nodes
  that do not yet have etcd data.
- Generate the etcd configuration file listing all zone nodes as cluster peers.
- Start the etcd systemd service on any node where it is not running.
- Add a node new to a running zone to the zone's etcd cluster, as a learner
  first, and promote it to a voting member once it has caught up.
- Restart running members one at a time when their configuration changes.

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
2. Ask each member with data which members its zone has, to find out whether
   the zone's etcd already runs and which of its nodes are new to it.
3. On a node without an etcd data directory, generate TLS certificates: a
   certificate authority (`ca.crt`), a peer key and certificate (`peer.key`,
   `peer.crt`), and a server key and certificate (`server.key`,
   `server.crt`). A node with etcd data keeps the certificates it has.
4. Generate the etcd configuration file at `{{ etcd_config_dir }}/etcd.yaml`
   with node identity, cluster membership for all nodes in the same zone, and
   network endpoints for client (port 2379) and peer (port 2380) communication.
5. Enable the etcd service and start it on every node where it is not
   running, other than one new to a running zone. A member started here reads the new configuration, and the role
   records it as the configuration that member runs.
6. Join each node new to a running zone, one at a time, as described in
   [Joining a Running Zone](#joining-a-running-zone), and then give it the
   same configuration as the rest of its zone.
7. Restart each running member whose configuration differs from the one it
   was last started with, one at a time. Before each restart the role checks
   that every member of the zone is healthy, and after it waits until they are
   again, then records the configuration the member now runs.

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

- `initial-cluster` lists every node in the zone.
- `initial-cluster-state` uses `new` for initial bootstrap. Only a node
  joining a running zone starts with `existing`, and only until it has joined.
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

### Joining a Running Zone

A zone's members bootstrap together, each with the whole zone in
`initial-cluster`, which only works while none of them hold any data. A node
added to the inventory of a zone that already runs cannot do that: the running
members would refuse it. The role adds it to the running cluster instead.

1. Add the node to the zone's cluster with `etcdctl member add --learner`. A
   learner receives the cluster's data but does not vote, so the zone's quorum
   does not change, and a node that fails to start costs the zone nothing.
2. Write a configuration for the node with the membership that etcd reports
   and `initial-cluster-state: existing`, and start etcd on it.
3. Promote the node to a voting member with `etcdctl member promote`, retrying
   until etcd judges it caught up with the leader.
4. Wait for every member of the zone to report healthy.
5. Write the node the same configuration as the rest of its zone, and restart
   the zone's members one at a time to read it.

Nodes join one at a time, because etcd takes one membership change at a time.
Every step is safe to repeat, so a run stopped partway through a join is
finished by the next: a node already added is not added again, and a learner
left unpromoted is promoted.

The role decides whether a node has data from its write-ahead log, as etcd
does, rather than from its data directory alone. It stops the run rather than
guess in two cases:

- Some members of a zone have data and the rest have none, but none of those
  with data answer. The zone may be running with every member stopped, or its
  first deployment may have failed partway, and the two need different fixes.
- A node with no data is still a started member of its zone's cluster. It
  has lost its data since it last ran, and its old membership has to be
  removed with `etcdctl member remove` before it can join again.

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
member whose file differs from the configuration it was last started with. It
restarts them one at a time, so the zone keeps its quorum and Patroni keeps its
leader lock. A run that changes nothing restarts nothing.

The role restarts a member whose file is newer than the etcd process, which it
reads from etcd's `process_start_time_seconds` metric, rather than only a member
whose file the run changed. If a run writes a member's new file but never
restarts the member, because the run was refused or stopped partway, the next
run restarts it. A member restarted by hand after its file changed counts as
running the new configuration.

The bootstrap settings in the file (`initial-cluster`, `initial-cluster-state`
and `initial-cluster-token`) are read only when a member starts with an empty
data directory, so re-rendering them on an existing member has no effect.

Certificates are issued only to a node without etcd data. An existing member
keeps the certificates it was built with.

!!! warning "Degraded zones"
    The role refuses to restart a member while any member of its zone is
    unhealthy, because taking a second member down can cost the zone its
    quorum. The new configuration is still written, and the next run restarts
    the member to apply it. Restore the zone to health and run the deployment
    again. A member that is stopped does not count against its zone here: the
    role starts it into the new configuration before restarting the others.

!!! warning "Removing Members"
    The role adds members to a zone but never removes them. A node taken out
    of the inventory stays a member of its zone's etcd cluster, and counts
    toward its quorum, until it is removed with `etcdctl member remove`.

!!! warning "Data Directory"
    The etcd data directory contains critical cluster state. Back up this
    directory before making cluster changes because loss of quorum makes the
    cluster unavailable.
