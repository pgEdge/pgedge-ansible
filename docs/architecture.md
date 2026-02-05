# Architecture

This page describes the cluster architectures supported by the pgEdge Ansible
Collection, including deployment patterns and design considerations.

## Overview

The pgEdge Ansible Collection supports multiple cluster topologies, from simple
multi-node setups to complex high-availability configurations with geographic
distribution. Understanding these patterns will help you choose the right
architecture for your requirements.

## Core Concepts

Deploying effective Postgres cluster architectures requires familiarity with 
the fundamental building blocks of the pgEdge Ansible Collection. These core 
concepts provide the foundational knowledge needed to properly configure and 
manage Postgres deployments across various topologies. The collection's 
architecture relies upon logical groupings and coordination mechanisms that 
ensure high availability, disaster recovery, and efficient replication.

### Zones

A zone represents a logical grouping of nodes, typically corresponding to a
data center, availability zone, or geographic region. Zones serve the
following purposes:

- Zones provide logical organization to group related nodes together.
- Each zone number becomes the Snowflake sequence ID for nodes in that zone.
- Patroni and etcd clusters form within each zone to define HA boundaries.
- Spock establishes subscriptions between zones for replication topology.

!!! tip "Zone Assignment"
    In simple clusters, use one node per zone. In HA clusters, assign multiple
    nodes to the same zone to form a Patroni cluster.

### Node Groups

The collection recognizes the following inventory groups:

- The `pgedge` group contains Postgres nodes in distributed replication.
- The `haproxy` group contains load balancer nodes for HA clusters.
- The `backup` group contains dedicated backup servers for pgBackRest.

## Architecture Patterns

The pgEdge Ansible Collection supports multiple cluster topologies designed to 
meet different requirements for availability, scalability, and geographic 
distribution. Each architecture pattern offers distinct advantages and 
trade-offs in terms of complexity, resource usage, and fault tolerance. 
Understanding these patterns makes it possible to select the most appropriate 
configuration for your specific use case, 

### Simple Three-Node Cluster

The simplest deployment consists of three pgEdge nodes in separate zones with
direct node-to-node replication.

![Simple 3-Node Cluster](img/simple-cluster.png)

This cluster type has the following characteristics:

- Each node resides in its own zone.
- Full mesh replication occurs between all nodes.
- No automatic failover exists within zones.
- Deployment and management are straightforward.

Use this cluster type for the following scenarios:

- Development, testing, or small production deployments benefit from simplicity.
- Low impact regional databases with active-active requirements work well.

!!! warning "Important"
    This cluster type is not recommended for production use. Without the
    protection of a physical replica, data loss can occur during node failure.

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
Patroni and etcd.

![Single Zone HA Cluster](img/ha-cluster-1-zone.png)

This cluster type has the following characteristics:

- Multiple nodes reside in a single zone.
- Automatic failover uses Patroni for leader election.
- Distributed consensus relies on etcd for coordination.
- HAProxy provides a single connection endpoint for applications.
- Streaming replication operates within the zone.
- No multi-zone replication occurs in this configuration.

Use this cluster type for the following scenarios:

- High availability within a single data center suits most workloads.
- Development and testing of HA features benefit from this topology.
- This topology serves as a prerequisite for multi-zone HA clusters.

In the following example, all nodes share the same zone to form a Patroni
cluster:

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

The most robust architecture combines HA within zones with distributed
replication between zones; this is the standard Ultra HA configuration.

![Two Zone Ultra HA Cluster](img/ultra-ha-cluster-2-zone.png)

This cluster type has the following characteristics:

- Multiple zones each contain their own Patroni cluster.
- Automatic failover occurs within each zone independently.
- Spock replication connects zones through HAProxy endpoints.
- Geographic distribution provides disaster recovery capabilities.
- High availability exists at both zone and cluster levels.
- The cluster survives complete zone failures without data loss.

Use this cluster type for the following scenarios:

- Multi-region deployments benefit from local write speeds.
- Environments requiring the highest HA guarantee use this topology.

The following example distributes two nodes across two zones with HAProxy
in each zone:

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

A hybrid cluster mixes single pgEdge nodes with HA deployments; this topology
is useful for testing or transitional deployments.

![Hybrid HA Cluster](img/ultra-ha-cluster-hybrid.png)

This cluster type has the following characteristics:

- The cluster contains a mix of simple and HA zones.
- Simple nodes connect directly to other nodes.
- HA nodes connect through HAProxy for load balancing.
- This topology provides flexibility for migration scenarios.
- Testing HA features becomes easier with this configuration.

## Component Architecture

The pgEdge Ansible Collection implements a layered architecture that combines 
proven Postgres technologies with modern orchestration practices to deliver 
robust and scalable database deployments. This component-based approach ensures 
that each layer serves a specific purpose in the overall architecture while 
maintaining clear separation of concerns. Understanding how these components 
interact provides insight into the collection's capabilities and helps in 
troubleshooting and optimization.

### Replication Stack

The collection uses a layered replication approach to maximize availability
and minimize write latency.

Streaming replication operates within zones with these characteristics:

- Patroni manages physical replication between nodes.
- Administrators can choose synchronous or asynchronous modes.
- Hot standby servers provide read scalability.
- Automatic failover activates when the primary fails.

Spock replication operates between zones with these characteristics:

- Logical multi-master replication enables writes on any node.
- Bidirectional data flow keeps all zones synchronized.
- Conflict detection and resolution handle concurrent writes.
- Row-level replication minimizes bandwidth usage.

### Backup Architecture

The collection supports a regional backup strategy where a backup server
targets nodes in the same region. Alternatively, backups may be transmitted
to a remote S3 store.

Backup options include the following:

- SSH mode provides dedicated backup servers per zone.
- S3 mode uses cloud object storage such as AWS S3 or compatible services.
- Per-zone backups ensure each zone maintains its own backup repository.
- Automated scheduling uses cron-based full and differential backups.

## Design Considerations

When implementing Postgres clusters with the pgEdge Ansible Collection, 
it's important to evaluate several factors to ensure optimal performance, 
reliability, and maintainability. These design considerations influence every 
aspect of your deployment, from initial topology selection to ongoing 
maintenance strategies. Addressing these factors proactively will help mitigate 
potential issues and ensure your cluster meets both current requirements and 
future scalability needs.

### Choosing a Topology

Consider these factors when selecting your architecture:

| Factor | Simple Cluster | HA Cluster | Ultra-HA |
|--------|----------------|------------|----------|
| Deployment Complexity | Low | Medium | High |
| Automatic Failover | No | Within zone | Within and between zones |
| Resource Requirements | 3+ nodes | 6+ nodes | 8+ nodes |
| Geographic Distribution | Yes | No | Yes |
| Maintenance Complexity | Low | Medium | High |
| Cost | Lower | Medium | Higher |

### Scalability

Adding nodes follows these patterns:

- Simple clusters add nodes to new zones for horizontal scaling.
- HA clusters add nodes to existing zones but require Patroni changes.
- Hybrid clusters mix approaches as needed for flexibility.

Adding zones follows these patterns:

- The cluster scales linearly with proper configuration.
- Each zone adds one subscription per existing zone.
- Total subscriptions equal n * (n-1) where n is the number of zones.

### Network Requirements

Consider network latency and bandwidth when planning your deployment:

- Connections within a zone require low latency for Patroni and etcd.
- Connections between zones tolerate higher latency based on lag tolerance.
- Bandwidth must be sufficient for replication traffic between zones.

### Consistency Models

Within an HA zone, operators can configure the following consistency options:

- Enable synchronous replication to achieve zero data loss.
- Synchronous mode ensures all writes reach at least one replica.
- Synchronous strict mode prevents writes if no replicas respond.

Between zones, the following consistency model applies:

- Asynchronous logical replication via Spock provides eventual consistency.
- Conflict resolution strategies handle concurrent writes to different zones.

## Best Practices

Avoid surprises by applying the following checklist to your pgEdge Ansible 
deployments:

- Start small by beginning with a simple cluster and migrate to HA later.
- Plan zones by aligning them with physical infrastructure boundaries.
- Test network latency and bandwidth between zones before deployment.
- Configure backups to separate infrastructure for all deployments.
- Implement monitoring for replication lag and cluster health.
- Document your specific topology and connection details for reference.

## Next Steps

- Review [configuration variables](configuration/index.md) for customization.
- Examine [sample playbooks](usage.md) for practical examples.
- Understand the [roles](roles/index.md) that implement these architectures.
