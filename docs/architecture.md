# Architecture

This page describes the cluster architectures supported by the pgEdge
Ansible Collection, including deployment patterns and design considerations.

## Overview

The pgEdge Ansible Collection supports multiple cluster topologies, from
simple multi-node setups to complex high-availability configurations with
geographic distribution. Understanding these patterns will help you choose
the right architecture for your requirements.

## Core Concepts

This section introduces the fundamental building blocks of the collection.

### Zones

A zone represents a logical grouping of nodes, typically corresponding to a
data center, availability zone, or geographic region. Zones serve the
following purposes:

- Zones provide logical organization to group related nodes together.
- Each zone number becomes the Snowflake sequence ID for nodes in that zone.
- Patroni and etcd clusters form within each zone to define HA boundaries.
- Spock establishes subscriptions between zones for replication topology.

In simple clusters, assign one node per zone. In HA clusters, assign multiple
nodes to the same zone to form a Patroni cluster.

### Node Groups

The collection recognizes the following inventory groups:

- The `pgedge` group contains Postgres nodes in distributed replication.
- The `haproxy` group contains load balancer nodes for HA clusters.
- The `backup` group contains dedicated backup servers for PgBackRest.

## Architecture Patterns

This section describes the four cluster topologies the collection supports.

### Simple Three-Node Cluster

The simplest deployment consists of three pgEdge nodes in separate zones
with direct node-to-node replication. This cluster type has the following
characteristics:

- Each node resides in its own zone.
- Full mesh replication occurs between all nodes via Spock.
- No automatic failover exists within zones.
- Deployment and management are straightforward.

This topology suits development, testing, and small production deployments
that require active-active writes without HA complexity. Without the
protection of a physical replica, data loss can occur during a node failure.

The following example assigns each node to a separate zone:

```yaml
pgedge:
  hosts:
    node1.example.com:
      zone: 1
    node2.example.com:
      zone: 2
    node3.example.com:
      zone: 3
```

### High-Availability Single-Zone Cluster

A single-zone HA cluster provides automatic failover within a zone using
Patroni and etcd. This cluster type has the following characteristics:

- Multiple nodes reside in a single zone.
- Automatic failover relies on Patroni for leader election.
- Distributed consensus relies on etcd for coordination.
- HAProxy provides a single connection endpoint for applications.
- Streaming replication operates within the zone.

This topology suits high-availability requirements within a single data
center and serves as a building block for multi-zone clusters.

The following example places all nodes in the same zone to form a Patroni
cluster:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
  hosts:
    node1.example.com:
      zone: 1
    node2.example.com:
      zone: 1
    node3.example.com:
      zone: 1

haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
```

### Ultra-HA Multi-Zone Cluster

The most robust architecture combines HA within zones with distributed
replication between zones. This cluster type has the following
characteristics:

- Multiple zones each contain their own Patroni cluster.
- Automatic failover occurs within each zone independently.
- Spock replication connects zones through HAProxy endpoints.
- Geographic distribution provides disaster recovery capabilities.
- The cluster survives complete zone failures without data loss.

This topology suits multi-region deployments and environments that require
the highest availability guarantee.

The following example distributes three nodes across two zones with HAProxy
and a dedicated backup server in each zone:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
  hosts:
    pg-z1-n1.example.com:
      zone: 1
    pg-z1-n2.example.com:
      zone: 1
    pg-z1-n3.example.com:
      zone: 1
    pg-z2-n1.example.com:
      zone: 2
    pg-z2-n2.example.com:
      zone: 2
    pg-z2-n3.example.com:
      zone: 2

haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
    proxy2.example.com:
      zone: 2

backup:
  hosts:
    backup1.example.com:
      zone: 1
    backup2.example.com:
      zone: 2
```

### Hybrid Cluster

A hybrid cluster mixes single pgEdge nodes with HA zones. This topology is
useful for testing HA features or for transitional deployments. It has the
following characteristics:

- The cluster contains a mix of simple and HA zones.
- Simple nodes connect directly to other nodes via Spock.
- HA nodes connect through HAProxy for proxied replication.
- This topology provides flexibility for migration scenarios.

## Replication Stack

The collection uses a layered replication approach to maximize availability
and minimize write latency.

Streaming replication operates within HA zones with these characteristics:

- Patroni manages physical replication between nodes in the same zone.
- Administrators can choose synchronous or asynchronous modes.
- Hot standby servers provide read scalability.
- Automatic failover activates when the primary fails.

Spock replication operates between zones with these characteristics:

- Logical multi-master replication enables writes on any zone.
- Bidirectional data flow keeps all zones synchronized.
- Conflict detection and resolution handle concurrent writes.
- Subscriptions target HAProxy endpoints so failover is transparent.

## Backup Architecture

The collection supports two backup strategies. The following options are
available:

- SSH mode stores backups on a dedicated backup server in each zone.
- S3 mode stores backups in a remote AWS S3 bucket or compatible service.

Per-zone stanzas ensure each zone maintains its own backup repository.
Automated cron entries schedule full and differential backups.

## Design Considerations

This section covers factors to consider when choosing a topology.

### Choosing a Topology

The following table compares the four topologies across key attributes:

| Factor | Simple | Single-Zone HA | Ultra-HA |
|--------|--------|----------------|----------|
| Deployment complexity | Low | Medium | High |
| Automatic failover | None | Within zone | Within and between zones |
| Minimum nodes | 3 | 4 | 8 |
| Geographic distribution | Yes | No | Yes |
| Maintenance complexity | Low | Medium | High |

### Scalability

Adding nodes to a simple cluster requires adding new zones for horizontal
scaling. Adding nodes to an existing HA zone requires careful Patroni
coordination; the pgEdge team recommends planning the final node count
during initial deployment.

Adding zones scales linearly. Each new zone adds one subscription per
existing zone; the total number of subscriptions equals n times (n-1),
where n is the number of zones.

### Consistency Models

Within an HA zone, the following synchronous options are available:

- Enable `synchronous_mode` so Patroni manages `synchronous_commit` based
  on cluster state.
- Enable `synchronous_mode_strict` to prevent writes when no synchronous
  replicas respond.

Between zones, Spock provides asynchronous logical replication with eventual
consistency and configurable conflict resolution.

## Next Steps

- The [Simple Cluster](simple_cluster.md) guide walks through a basic
  three-node deployment.
- The [Ultra-HA Cluster](ultra_ha.md) guide covers the full production
  topology.
- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
