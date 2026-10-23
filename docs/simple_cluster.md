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

Every node in the cluster can also run a pgBouncer connection pooler, giving it
a second endpoint on port 6432 beside PostgreSQL's own on 5432. Pooling is
opt-in and cluster-wide, like `is_ha_cluster`: set `pgbouncer_enabled` on the
`pgedge` group and every node gets a pooler in front of its own PostgreSQL.

The following inventory pools all three nodes:

```yaml
all:
  vars:
    ansible_user: pgedge

pgedge:
  vars:
    db_password: secret
    pgbouncer_enabled: true
    pgbouncer_auth_password: poolsecret
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3
```

`pgbouncer_auth_password` is the pooler's own PostgreSQL login. It is the one
password the collection writes to disk, and the playbook refuses to run while
it is still the default `secret`, so set it here or take it from a vault.

Add the two pooling roles to the playbook, gated on `pgbouncer_enabled` so a
cluster that does not pool is untouched:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_repos
    - install_pgedge
    - role: install_pgbouncer
      when: pgbouncer_enabled | bool
    - setup_postgres
    - role: setup_pgbouncer
      when: pgbouncer_enabled | bool
    - setup_pgedge
```

After the playbook completes, every node answers on two ports. Clients choose
which one they want:

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

## Adding ColdFront Tiered Storage

ColdFront keeps recent data in native Postgres partitions and archives older
data to Apache Iceberg on S3-compatible storage, readable and writable through
the same SQL. It is optional, so it has a sample playbook and inventory of its
own, in `sample-playbooks/simple-cluster-coldfront`, beside the plain
`simple-cluster` ones. Set `coldfront_enabled` on the `pgedge` group, and
put the host that serves the Lakekeeper Iceberg catalog, which every cold-tier
commit goes through, in a `lakekeeper` group of its own. The collection
deploys no object store, so point the `coldfront_s3_*` settings at one that
already exists, with its bucket created.

The following inventory adds ColdFront to all three nodes:

```yaml
all:
  vars:
    ansible_user: pgedge
    lakekeeper_host: 192.168.6.20
    coldfront_s3_endpoint: https://s3.example.com
    coldfront_s3_bucket: iceberg
    coldfront_s3_access_key: coldfront
    coldfront_s3_secret_key: secret

pgedge:
  vars:
    db_password: secret
    coldfront_enabled: true
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3

lakekeeper:
  vars:
    lakekeeper_db_password: catalogsecret
  hosts:
    192.168.6.20:
```

Both groups read the catalog and object store settings, so they go under
`all`. For AWS S3, leave `coldfront_s3_endpoint` empty, set
`coldfront_s3_region`, and set `coldfront_s3_path_style` to `false`. With
`coldfront_mesh` at its default of `false`, each node serializes only its own
cold-tier commits, so write any one Iceberg table from a single node. Set
`coldfront_mesh` to `true`, and add `coldfront_db` to `db_names`, to order
commits across every node instead.

Add a play for the Lakekeeper host ahead of the pgEdge nodes, since
`setup_coldfront` fails if the catalog is not already serving, and add the
three ColdFront roles to the `pgedge` play.
`install_coldfront` comes before `setup_postgres`, which preloads ColdFront's
libraries, `setup_coldfront_db` follows `setup_postgres` to create ColdFront's
database and extensions, and `setup_coldfront` comes after `setup_pgedge`:

```yaml
- hosts: lakekeeper

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_repos
    - install_lakekeeper
    - setup_lakekeeper

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - init_server
    - install_repos
    - install_pgedge
    - install_coldfront
    - setup_postgres
    - setup_coldfront_db
    - setup_pgedge
    - setup_coldfront
```

The `sample-playbooks/simple-cluster-coldfront` playbook includes both. See
[ColdFront Configuration](configuration/coldfront.md) for the catalog, object
store and ColdFront parameters.
