# Deploying a Simple Cluster

This guide describes how to deploy a standard three-node pgEdge Distributed
Postgres cluster using the sample playbook included with the collection.

Our simple cluster consists of three pgEdge nodes, each in a separate zone.
Spock logical replication runs between all nodes so that writes on any node
are replicated to every other node. This topology does not include HA
components such as etcd, Patroni, or HAProxy.

## Creating an Inventory File

Create an inventory file that defines your three nodes and assigns each to a
distinct zone. The following example inventory uses IP addresses as host
identifiers:

```yaml
all:
  vars:
    ansible_user: pgedge

pgedge:
  vars:
    db_password: secret
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3
```

The `zone` variable must be unique per node. Zones also serve as Snowflake
node IDs, so each node in the cluster must have a distinct integer value.

## Creating a Playbook

Create a playbook file that applies the required roles in order. The following
example deploys a simple three-node cluster:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_pgedge
    - setup_postgres
    - setup_pgedge
```

## Running the Playbook

Run the playbook with the following command, substituting your inventory file
path:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

After the playbook completes, each node will have a running PostgreSQL
instance with Spock and Snowflake extensions installed. All nodes will be
subscribed to each other for bidirectional logical replication.

## Configuring the Cluster

Override default parameters by setting variables in the inventory or playbook.
The following example inventory configures PostgreSQL 17 with a custom
database name and user:

```yaml
pgedge:
  vars:
    pg_version: 17
    db_names:
      - mydb
    db_user: myuser
    db_password: mypassword
```

A complete list of parameters is available in the
[Configuration Reference](configuration.md).

## Next Steps

- The [Ultra-HA Cluster](ultra_ha.md) guide describes deploying a
  production-grade multi-zone HA cluster.
- The [Configuration Reference](configuration.md) lists all available parameters
  and their defaults.
- The [Role Reference](roles.md) describes what each role does and when to use
  it.
