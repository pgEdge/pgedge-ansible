# pgEdge Distributed Postgres Ansible Collection

Welcome to the documentation for the pgEdge Distributed Postgres Ansible
Collection. This collection provides Ansible roles designed to automate the
deployment and management of pgEdge Distributed Postgres clusters.

## What This Collection Provides

This collection automates the entire deployment lifecycle of pgEdge clusters.
The lifecycle automation includes the following features:

- Server initialization prepares systems with required packages and settings.
- Postgres installation deploys the database with pgEdge enhancements.
- High availability setup provides optional Patroni, etcd, and HAProxy support.
- Distributed replication configures Spock-based multi-master replication.
- Backup management integrates pgBackRest for enterprise-grade backups.

## Key Features

This collection offers several key capabilities for deployment. The collection
includes the following features:

- Flexible deployment options enable both simple and complex configurations.
- Multi-platform compatibility supports Debian, RedHat, and related distros.
- Extensive parameters provide customization for your cluster configuration.
- Backup automation and failover capabilities ensure production readiness.
- Idempotent operations allow safe re-running of playbooks for updates.

## Supported Cluster Topologies

This collection supports multiple cluster architectures for different needs.
The following topologies are available:

- Simple clusters provide direct node-to-node replication for basic setups.
- High-availability clusters use Patroni-managed Postgres with failover.
- Hybrid clusters combine simple and HA nodes for testing or migration.
- Multi-zone clusters enable geographic distribution with zone awareness.

## Quick Start

The best way to get started with this collection is to follow these steps:

1. Install the collection by following the 
   [installation guide](installation.md).
2. Review the [architecture patterns](architecture.md) to choose your model.
3. Configure your [inventory and variables](configuration/index.md) as needed.
4. Explore the [Ansible role documentation](roles/index.md) to understand 
   components.
5. Run your playbook to deploy your cluster.

## Documentation Structure

This collection documentation provides several curated topic areas to assist in 
successful cluster deployment:

- [Installation](installation.md) covers prerequisites and installation steps.
- [Architecture](architecture.md) describes cluster design patterns and types.
- [Configuration](configuration/index.md) provides a complete variable 
  reference.
- [Roles](roles/index.md) contains detailed documentation for each Ansible role.
- [Usage Examples](usage.md) demonstrates playbooks and deployment scenarios.
- [Troubleshooting](troubleshooting/index.md) provides solutions to common issues.

## Getting Help

For issues, questions, or contributions, visit the
[GitHub repository](https://github.com/pgEdge/pgedge-ansible).

!!! note "Early Stage Software"
    These roles remain in active development and will undergo revisions as they
    mature. The roles function correctly but may not fully recover if errors
    occur during execution. Future versions will improve error handling and
    recovery capabilities.
