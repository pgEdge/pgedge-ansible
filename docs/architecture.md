# Architecture

This page describes the various cluster architectures supported by the pgEdge Ansible Collection, including deployment patterns, component relationships, and design considerations.

## Overview

The pgEdge Ansible Collection supports multiple cluster topologies, from simple multi-node setups to complex high-availability configurations with geographic distribution. Understanding these patterns will help you choose the right architecture for your requirements.

## Core Concepts

### Zones

A **zone** represents a logical grouping of nodes, typically corresponding to a data center, availability zone, or geographic region. Zones serve the following purposes:

- Logical organization to group related nodes together
- Snowflake IDs where each zone number becomes the sequence ID for nodes in that zone
- HA boundaries where Patroni/etcd clusters are formed within each zone
- Replication topology where subscriptions are established between zones

!!! tip "Zone Assignment"
    In simple clusters, use one node per zone. In HA clusters, assign multiple nodes to the same zone to form a Patroni cluster.

### Node Groups

The collection recognizes the following inventory groups:

- pgedge: PostgreSQL nodes that participate in distributed replication
- haproxy: Load balancer nodes for HA clusters (optional)
- backup: Dedicated backup servers for pgBackRest (optional)

## Architecture Patterns

### Simple Three-Node Cluster

The simplest deployment consists of three pgEdge nodes in separate zones with direct node-to-node replication.

![Simple 3-Node Cluster](img/simple-cluster.png)

**Characteristics:**

- Each node is in its own zone
- Full mesh replication between all nodes
- No automatic failover within zones
- Simple to deploy and manage

**Use Cases:**

- Development, testing, or small production deployments
- Low impact regional databases with active-active requirements

!!! warning "Important"
    This type of cluster is not recommended for production use. Since no nodes are protected by a physical replica, it's possible to experience data loss in the event of node failure.

**Inventory Example:**

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

A single-zone HA cluster provides automatic failover within a zone using Patroni and etcd.

![Single Zone HA Cluster](img/ha-cluster-1-zone.png)

**Characteristics:**

- Multiple nodes in a single zone
- Automatic failover using Patroni
- Distributed consensus with etcd
- HAProxy provides single connection endpoint
- Streaming replication within the zone
- No multi-zone replication

**Use Cases:**

- High availability within a single data center
- Development/testing of HA features
- Prerequisites for multi-zone HA clusters

**Inventory Example:**

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    zone: 1
  hosts:
    node1.example.com:
    node2.example.com:
    node3.example.com:
```

### Ultra-HA Multi-Zone Cluster

The most robust architecture combines HA within zones with distributed replication between zones, which is our standard Ultra HA configuration.

![Two Zone Ultra HA Cluster](img/ultra-ha-cluster-2-zone.png)

**Characteristics:**

- Multiple zones, each with its own Patroni cluster
- Automatic failover within each zone
- Spock replication between zones through HAProxy
- Geographic distribution for disaster recovery
- High availability at both zone and cluster levels
- Survives complete zone failures

**Use Cases:**

- Multi-region deployments that need local write speeds
- Environments that need the highest HA guarantee

**Inventory Example:**

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
    node4.example.com:
      zone: 2
    node5.example.com:
      zone: 2
    node6.example.com:
      zone: 2

haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
    proxy2.example.com:
      zone: 2
```

### Hybrid Cluster

A hybrid cluster mixes single pgEdge nodes with HA deployments, useful for testing or transitional deployments.

![Hybrid HA Cluster](img/ultra-ha-cluster-hybrid.png)

**Characteristics:**

- Mix of simple and HA zones
- Simple nodes connect directly
- HA nodes connect through HAProxy
- Flexible for migration scenarios
- Useful for testing HA features

## Component Architecture

### Replication Stack

The collection uses a layered replication approach to maximize availability and minimize write latency.

**Streaming Replication (within zone):**

- Physical replication managed by Patroni
- Synchronous or asynchronous modes available
- Provides hot standby servers
- Automatic failover on primary failure

**Spock Replication (between zones):**

- Logical multi-master replication
- Bidirectional data flow
- Conflict detection and resolution
- Row-level replication

### Backup Architecture

The collection currently supports a regional backup strategy, where a backup server will target nodes in the same region. Alternatively, backups may be transmitted to a remote S3 store.

Backup options include the following:

- SSH mode: Dedicated backup servers per zone
- S3 mode: Cloud object storage (AWS S3 or compatible)
- Per-zone backups: Each zone maintains its own backup repository
- Automated scheduling: Cron-based full and differential backups

## Design Considerations

### Choosing a Topology

Consider these factors when selecting your architecture:

| Factor | Simple Cluster | HA Cluster | Ultra-HA |
|--------|----------------|------------|----------|
| **Deployment Complexity** | Low | Medium | High |
| **Automatic Failover** | No | Within zone | Within & between zones |
| **Resource Requirements** | 3+ nodes | 6+ nodes | 8+ nodes |
| **Geographic Distribution** | Yes | No | Yes |
| **Maintenance Complexity** | Low | Medium | High |
| **Cost** | Lower | Medium | Higher |

### Scalability

**Adding Nodes:**

- Simple clusters: Add nodes to new zones
- HA clusters: Add nodes to existing zones (requires Patroni reconfiguration)
- Hybrid: Mix approaches as needed

**Adding Zones:**

- Scales linearly with proper configuration
- Each zone adds one subscription per existing zone
- Total subscriptions = n * (n-1) where n = number of zones

### Network Requirements

Consider network latency and bandwidth:

- **Within zone**: Low latency required for Patroni/etcd (<10ms recommended)
- **Between zones**: Higher latency tolerable (depends on replication lag tolerance)
- **Bandwidth**: Sufficient for replication traffic between zones

### Consistency Models

**Within HA Zone:**

- Can be configured for synchronous replication
- Synchronous mode ensures zero data loss within zone
- Synchronous strict mode prevents writes if replicas unavailable

**Between Zones:**

- Asynchronous logical replication via Spock
- Eventual consistency model
- Conflict resolution strategies available

## Best Practices

1. Start simple by beginning with a simple cluster and migrating to HA when needed.
2. Plan zones by aligning them with physical infrastructure boundaries.
3. Test network latency and bandwidth between zones before deployment.
4. Configure backups, preferably to separate infrastructure, for all deployments.
5. Implement monitoring for replication lag and cluster health.
6. Document your specific topology and connection details for reference.

## Next Steps

- Review [configuration variables](configuration.md) to customize your deployment
- Examine [sample playbooks](usage.md) for practical examples
- Understand the [roles](roles/index.md) that implement these architectures
