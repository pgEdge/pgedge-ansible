# Deploying a Simple Cluster

This guide describes how to deploy a standard three-node pgEdge Distributed
Postgres cluster using the sample playbook included with the collection.

Our simple cluster consists of three pgEdge nodes, each in a separate zone.
Spock logical replication runs between all nodes so that writes on any node
are replicated to every other node. This topology does not include HA
components such as etcd, Patroni, or HAProxy.

## Creating an Inventory File

Before running a playbook, create an inventory file that defines your three
nodes and assigns each to a distinct zone. The following example of an
inventory file uses IP addresses as host identifiers:

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
node IDs, so ensure that each node in the cluster has a distinct integer
value.

## Creating a Playbook

Create a playbook file that applies the required roles in order. The following
example deploys a simple three-node cluster:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_repos
    - install_pgedge
    - setup_postgres
    - setup_pgedge
```

## Running the Playbook

Run the playbook with the following command, substituting your inventory file
name and path:

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

## Adding Connection Pooling

Any node in the cluster can also run a pgBouncer connection pooler, giving it a
second endpoint on port 6432 beside PostgreSQL's own on 5432. Pooling is
opt-in: add the nodes that should run a pooler to a `pgbouncer` group, which
must be a subset of `pgedge`.

The following inventory pools two of the three nodes:

```yaml
all:
  vars:
    ansible_user: pgedge

pgedge:
  vars:
    db_password: secret
    pgbouncer_auth_password: poolsecret
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3

pgbouncer:
  hosts:
    192.168.6.10:
    192.168.6.11:
```

`pgbouncer_auth_password` is the pooler's own PostgreSQL login. It is the one
password the collection writes to disk, and the playbook refuses to run while
it is still the default `secret`, so set it here or take it from a vault.

Add the two pooling roles to the playbook, gated on group membership so the
unpooled node is untouched:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_repos
    - install_pgedge
    - role: install_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
    - setup_postgres
    - role: setup_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
    - setup_pgedge
```

After the playbook completes, each pooled node answers on two ports. Clients
choose which one they want:

```bash
# Direct connection to PostgreSQL
psql -h 192.168.6.10 -p 5432 -U admin demo

# Pooled connection through pgBouncer
psql -h 192.168.6.10 -p 6432 -U admin demo
```

The two endpoints are not interchangeable. They enforce separate client
authentication rules, so a client that reaches one is not automatically
admitted to the other, and nothing fails a pooled connection over to
PostgreSQL. Out of the box the pooled endpoint admits the cluster's own nodes
and local administration; name any other client in `pgbouncer_hba_rules` to
admit it to the pooled endpoint, or in `custom_hba_rules` to admit it to both.

Every PostgreSQL role works through the pooler, including roles created after
deployment, because the pooler looks each client's stored credential up rather
than keeping a password list of its own. See
[Pooling Configuration](configuration/pooling.md) for the pool mode, TLS, and
sizing parameters.
