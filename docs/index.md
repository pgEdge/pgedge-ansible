# pgEdge Ansible Collection

The pgEdge Ansible Collection provides a set of Ansible roles for
deploying and configuring pgEdge Distributed Postgres clusters. The
collection automates the provisioning of single-zone clusters and
multi-zone High Availability clusters with optional load balancing
and automated backup.

## Overview

The collection includes roles for every stage of cluster deployment,
from initial server preparation through PostgreSQL initialization,
HA configuration, and backup setup. Roles are designed to compose
into playbooks that match your topology - from a simple three-node
cluster to a production-grade multi-zone HA deployment with HAProxy
and PgBackRest.

The collection supports the following deployment topologies:

- A simple multi-node pgEdge Distributed Postgres cluster.
- An Ultra-HA cluster with multiple nodes per zone, etcd, Patroni,
  HAProxy, and dedicated backup servers.

## Compatibility

The collection has been validated on the following Linux platforms:

- Debian 12 (Bookworm)
- Rocky 9

The collection may also work on other Debian or RHEL variants, but
compatibility with those distributions has not been validated.

## Next Steps

- The [Installation](installation.md) page describes how to install
  the collection and its prerequisites.
- The [Simple Cluster](simple_cluster.md) guide walks through deploying
  a basic three-node pgEdge Distributed Postgres cluster.
- The [Ultra-HA Cluster](ultra_ha.md) guide describes deploying a
  production-grade multi-zone HA cluster.
- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
