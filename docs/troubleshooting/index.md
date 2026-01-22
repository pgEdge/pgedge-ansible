# Troubleshooting

This guide provides solutions to common issues encountered when deploying and
managing pgEdge clusters with the Ansible Collection. The troubleshooting
documentation is organized by component and deployment phase; this structure
allows administrators to quickly locate solutions for specific problems during
cluster provisioning and operation.

Each section addresses a distinct layer of the pgEdge stack, from foundational
Ansible setup through service-specific configuration. These guides provide
step-by-step diagnostic procedures and proven solutions for debugging initial
connectivity issues and resolving complex replication problems.

## Ansible Execution

Addresses Ansible-specific execution challenges including playbook failures,
connectivity testing, check mode limitations, role debugging, and dependency
management. This section also provides guidance on getting additional help
through GitHub issues and community resources.

[Ansible Execution](ansible.md)

## Collection Installation

Covers foundational problems that block cluster deployment before it begins.
This section addresses Ansible collection installation failures, build process
errors, and SSH connectivity challenges between the control node and managed
hosts. Start here if Ansible cannot locate the pgEdge collection or fails to
connect to target systems.

[Installation Issues](installation.md)

## pgEdge Software Repository

Addresses package repository setup problems that prevent software installation.
This section covers network connectivity to pgEdge repositories, firewall
configuration for HTTPS access, GPG key import failures, and package cache
synchronization issues. Consult this guide when target hosts cannot download
packages from pgEdge repositories.

[Repository Configuration](repository.md)

## Package Installation

Resolves package installation failures that occur after successful repository
configuration. This section covers "package not found" errors, version
mismatches, dependency conflicts with existing Postgres installations, network
timeouts during downloads, and cron package conflicts. Use this guide when
packages exist in repositories but installation fails.

[Package Installation](package.md)

## System Hosts

Addresses system-level configuration challenges including SELinux settings, SSH
key management, and hostname resolution. This section covers issues that arise
when Ansible attempts to modify fundamental system components, particularly in
environments with strict security policies or custom configurations.

[System Configuration](system.md)

## etcd

Covers the distributed coordination backend that manages cluster state and
leader election. This section addresses etcd download failures, checksum
verification errors, binary permission problems, service startup issues, and
cluster formation failures. Consult this guide when etcd nodes cannot
communicate or agree on cluster state.

[etcd Configuration](etcd.md)

## HAProxy

Addresses the connection routing layer that directs traffic to the primary
Postgres node. This section covers HAProxy service failures, health check
problems, connection routing issues, and statistics dashboard access. Use this
guide when clients cannot connect through HAProxy or connections route to
incorrect nodes.

[HAProxy Configuration](haproxy.md)

## Patroni

Addresses the high-availability controller that orchestrates Postgres
failover and replica management. This section covers pipx installation
problems, Patroni package failures, binary path issues, configuration errors,
etcd connectivity problems, and replication challenges. Use this guide when
Patroni fails to start or cannot form a proper HA cluster.

[Patroni Installation and Configuration](patroni.md)

## Postgres

Resolves database-specific issues including initialization failures, SSL
certificate generation, service startup problems, and extension installation
errors. This section covers Postgres configuration at the core of the pgEdge
deployment. Consult this guide when Postgres services fail to start or accept
connections.

[Postgres Configuration](postgres.md)

## Spock Extension

Covers multi-region synchronization issues in pgEdge deployments. This section
addresses Spock node creation failures, subscription problems, proxy
connectivity issues, synchronization delays, and disabled subscription states.
Consult this guide when data fails to replicate between Postgres instances.

[Spock Replication](spock.md)

## Backup and Recovery

Resolves backup infrastructure problems including pgBackRest configuration,
SSH connectivity to backup servers, S3 repository access, WAL archiving
failures, and backup user authentication. Use this guide when backup operations
fail or restoration procedures encounter errors.

[Backup and Recovery](backup.md)
