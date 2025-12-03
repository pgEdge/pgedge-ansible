# pgEdge Distributed Postgres Ansible Collection

Welcome to the documentation for the pgEdge Distributed Postgres Ansible Collection. This collection provides a comprehensive set of Ansible roles designed to automate the deployment and management of pgEdge Distributed Postgres clusters.

## What This Collection Provides

This Ansible collection automates the entire deployment lifecycle of pgEdge clusters, including:

- **Server initialization** - Prepares servers with required packages and configurations
- **PostgreSQL installation** - Deploys PostgreSQL with pgEdge enhancements
- **High availability** - Optional setup with Patroni, etcd, and HAProxy
- **Distributed replication** - Configures Spock-based multi-master replication
- **Backup management** - Integrates pgBackRest for enterprise-grade backups

## Key Features

- **Flexible deployment options**: Deploy simple multi-node clusters or complex high-availability configurations
- **Multi-platform support**: Works with Debian, RedHat, and related distributions
- **Comprehensive configuration**: Extensive parameters for customizing your cluster
- **Production-ready**: Includes backup automation, monitoring endpoints, and failover capabilities
- **Idempotent operations**: Safe to re-run playbooks for configuration updates

## Supported Cluster Topologies

The collection supports multiple cluster architectures:

- **Simple clusters**: Direct node-to-node replication for straightforward deployments
- **High-availability clusters**: Patroni-managed PostgreSQL with automatic failover within zones
- **Hybrid clusters**: Mix of simple and HA nodes for testing or gradual migration
- **Multi-zone clusters**: Geographic distribution with zone-aware replication

## Quick Start

To get started with the pgEdge Ansible Collection:

1. [Install the collection](installation.md) on your Ansible control node
2. Review the [architecture patterns](architecture.md) to choose your deployment model
3. Configure your [inventory and variables](configuration.md)
4. Explore the [roles documentation](roles/index.md) to understand each component
5. Run your playbook to deploy your cluster

## Documentation Structure

- **[Installation](installation.md)** - Prerequisites and installation steps
- **[Architecture](architecture.md)** - Cluster design patterns and topologies
- **[Configuration](configuration.md)** - Complete variable reference
- **[Roles](roles/index.md)** - Detailed documentation for each Ansible role
- **[Usage Examples](usage.md)** - Sample playbooks and deployment scenarios

## Getting Help

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/pgEdge/pgedge-ansible).

!!! note "Early Stage Software"
    These roles are in active development and will undergo revisions as they mature. While functional, they may not be fully re-entrant if errors occur during execution. Future versions will improve error handling and recovery capabilities.
