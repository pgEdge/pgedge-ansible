# pgEdge Distributed Postgres Ansible Collection

Welcome to the documentation for the pgEdge Distributed Postgres Ansible Collection. This collection provides a comprehensive set of Ansible roles designed to automate the deployment and management of pgEdge Distributed Postgres clusters.

## What This Collection Provides

This collection automates the entire deployment lifecycle of pgEdge clusters. The lifecycle automation includes the following features:

- Server initialization prepares systems with the required packages and configurations.
- PostgreSQL installation deploys the database with pgEdge enhancements.
- High availability setup provides optional Patroni, etcd, and HAProxy integration.
- Distributed replication configures Spock-based multi-master replication.
- Backup management integrates pgBackRest for enterprise-grade backups.

## Key Features

This collection offers several key capabilities for deployment. The collection includes the following features:

- Support for flexible deployment options enables both simple and complex configurations.
- Multi-platform compatibility works with Debian, RedHat, and related Linux distributions.
- Extensive parameters provide customization for your cluster configuration.
- Backup automation, monitoring endpoints, and failover capabilities ensure production readiness.
- Idempotent operations allow safe re-running of playbooks for configuration updates.

## Supported Cluster Topologies

This collection supports multiple cluster architectures for different deployment needs. The following topologies are available:

- Simple clusters provide direct node-to-node replication for straightforward deployments.
- High-availability clusters use Patroni-managed PostgreSQL with automatic failover within zones.
- Hybrid clusters combine simple and HA nodes for testing or gradual migration.
- Multi-zone clusters enable geographic distribution with zone-aware replication capabilities.

## Quick Start

To get started with the pgEdge Ansible Collection:

1. Install the collection on your Ansible control node by following the [installation guide](installation.md).
2. Review the [architecture patterns](architecture.md) to choose your deployment model.
3. Configure your [inventory and variables](configuration.md) according to your requirements.
4. Explore the [roles documentation](roles/index.md) to understand each component.
5. Run your playbook to deploy your cluster.

## Documentation Structure

The documentation is organized into the following sections:

- The [Installation](installation.md) section covers prerequisites and installation steps.
- The [Architecture](architecture.md) section describes cluster design patterns and topologies.
- The [Configuration](configuration.md) section provides a complete variable reference.
- The [Roles](roles/index.md) section contains detailed documentation for each Ansible role.
- The [Usage Examples](usage.md) section demonstrates sample playbooks and deployment scenarios.

## Getting Help

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/pgEdge/pgedge-ansible).

!!! note "Early Stage Software"
    These roles are in active development and will undergo revisions as they mature. While functional, they may not be fully re-entrant if errors occur during execution. Future versions will improve error handling and recovery capabilities.
