# Deploying an Ultra-HA Cluster

This guide describes how to deploy a production-grade pgEdge Distributed
Postgres cluster with High Availability using the Ultra-HA sample playbook
included with the collection.

## Overview

An Ultra-HA cluster organizes nodes into two or more zones. Each zone contains
multiple pgEdge nodes managed by Patroni for automatic failover, with etcd
providing distributed coordination. HAProxy nodes in each zone route client
connections to the current primary and survive PostgreSQL failover events.
Dedicated backup servers in each zone run PgBackRest for automated backup and
WAL archival.

The standard Ultra-HA topology per zone includes:

- Three pgEdge nodes (managed by Patroni and etcd).
- One HAProxy node (routes connections to the Patroni primary).
- One backup server (stores PgBackRest repository).

A two-zone Ultra-HA deployment therefore requires ten nodes in total.

## Creating an Inventory File

Create an inventory file that defines all nodes in each host group. Each
pgEdge node must have a `zone` variable. HAProxy and backup nodes must also be
assigned to the same zone as the pgEdge nodes they support. The following
example inventory defines a two-zone cluster:

```yaml
all:
  vars:
    ansible_user: pgedge

pgedge:
  vars:
    db_password: secret
    is_ha_cluster: true
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 1
    192.168.6.12:
      zone: 1
    192.168.6.13:
      zone: 2
    192.168.6.14:
      zone: 2
    192.168.6.15:
      zone: 2

haproxy:
  hosts:
    192.168.6.16:
      zone: 1
    192.168.6.17:
      zone: 2

backup:
  hosts:
    192.168.6.18:
      zone: 1
    192.168.6.19:
      zone: 2
```

Setting `is_ha_cluster: true` on the `pgedge` group instructs the roles to
install and configure etcd, Patroni, and HAProxy. The first node listed per
zone bootstraps the Patroni cluster; all remaining nodes in the zone are
rebuilt as streaming replicas.

## Creating a Playbook

Create a playbook that applies roles in the correct order. The following
example playbook deploys the full Ultra-HA topology:

```yaml
- hosts: pgedge, haproxy, backup

  collections:
    - pgedge.platform

  roles: []

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_pgedge
    - setup_postgres
    - install_etcd
    - install_patroni
    - install_backrest
    - setup_etcd
    - setup_patroni

- hosts: haproxy

  collections:
    - pgedge.platform

  roles:
    - init_server
    - setup_haproxy

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - setup_pgedge
    - setup_backrest

- hosts: backup

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_pgedge
    - install_backrest
    - setup_backrest
```

HAProxy must be configured before `setup_pgedge` runs so that Spock
subscriptions target the proxy layer. This ensures subscriptions survive a
Patroni failover without requiring manual resubscription.

## Running the Playbook

Run the playbook with the following command, substituting your inventory file
path:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

## High-Availability Behavior

After deployment, the following HA behaviors are active:

- Patroni monitors PostgreSQL health in each zone and promotes a replica if
  the primary fails.
- HAProxy health-checks the Patroni REST API and routes connections only to
  the current primary.
- Spock subscriptions run through HAProxy so cross-zone replication continues
  after a failover.
- PgBackRest archives WAL continuously and runs scheduled full and differential
  backups.

## Adding a Backup Configuration

By default, backups use SSH to transmit data to the dedicated backup server in
each zone. To use AWS S3 instead, set `backup_repo_type` to `s3` and supply
the required parameters:

```yaml
backup_repo_type: s3
backup_repo_path: /backrest
backup_repo_params:
  region: us-east-1
  endpoint: s3.amazonaws.com
  bucket: my-pgbackrest-bucket
  access_key: AKIAIOSFODNN7EXAMPLE
  secret_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

A complete list of backup parameters is available in the
[Configuration Reference](configuration.md).

## Next Steps

- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
- The [Role Reference](roles.md) describes what each role does and when to use
  it.
