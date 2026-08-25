# Deploying an Ultra-HA Cluster

This guide describes how to deploy a production-grade pgEdge Distributed
Postgres cluster with high availability using the Ultra-HA sample playbook
included with the collection.

An Ultra-HA cluster organizes nodes into two or more zones. Each zone contains
multiple pgEdge nodes managed by Patroni for automatic failover, with etcd
providing distributed coordination. HAProxy nodes in each zone route client
connections to the current primary and survive PostgreSQL failover events.
Dedicated backup servers in each zone run pgBackRest for automated backup and
WAL archival.

The standard Ultra-HA topology per zone includes:

- Three pgEdge nodes (managed by Patroni and etcd).
- One HAProxy node (routes connections to the Patroni primary).
- One backup server (stores pgBackRest repository).

A two-zone Ultra-HA deployment therefore requires ten nodes in total.

After deployment, the following HA behaviors are active:

- Patroni monitors PostgreSQL health in each zone and promotes a replica if
  the primary fails.
- HAProxy health-checks the Patroni REST API and routes connections only to
  the current primary.
- Spock subscriptions run through HAProxy so cross-zone replication continues
  after a failover.
- PgBackRest archives WAL continuously and runs scheduled full and differential
  backups.


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
    pgedge_password: secret
    replication_password: secret
    backup_password: secret
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

Note that these playbooks will also require that the passwords be changed from
`secret`.

## Creating a Playbook

Create a playbook that applies roles in the correct order. The following
example playbook deploys the full Ultra-HA topology:

```yaml
- hosts: all

  collections:
    - pgedge.platform

  roles:
    - init_server

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
    - install_etcd
    - install_patroni
    - install_backrest
    - setup_etcd
    - setup_patroni
    - setup_backrest

- hosts: haproxy

  collections:
    - pgedge.platform

  roles:
    - setup_haproxy

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - setup_pgedge

- hosts: backup

  collections:
    - pgedge.platform

  roles:
    - install_repos
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


## Adding a Backup Configuration

By default, backups use SSH to transmit data to the dedicated backup server in
each zone. To use AWS S3 instead, update your configuration, setting
`backup_repo_type` to `s3` and supplying the required parameters:

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


## Adding Connection Pooling

pgEdge nodes can also run a pgBouncer connection pooler, and HAProxy fronts the
poolers on `pooler_port` the way it fronts PostgreSQL on `proxy_port`. Pooling
is opt-in: add the nodes that should run a pooler to a `pgbouncer` group, which
must be a subset of `pgedge`.

Pool every node of a zone, or none of them. The pooled HAProxy listener
health-checks Patroni's leader endpoint, exactly as the direct listener does,
so it routes only to the pooler on the current leader, and a failover to an
unpooled node would leave the pooled endpoint with no reachable backend.

Add the group to the inventory:

```yaml
pgedge:
  vars:
    pgbouncer_auth_password: "{{ vault_pgbouncer_auth_password }}"
  # ... hosts as above ...

pgbouncer:
  hosts:
    192.168.6.10:
    192.168.6.11:
    192.168.6.12:
    192.168.6.13:
    192.168.6.14:
    192.168.6.15:
```

`pgbouncer_auth_password` is the pooler's own PostgreSQL login, the one
password the collection writes to disk. The playbook refuses to run while it is
still the default.

Then add the two pooling roles to the `pgedge` play, gated on group membership.
`install_pgbouncer` goes with the other install roles, and `setup_pgbouncer`
after `setup_patroni`, because the pooler forwards to the PostgreSQL instance
Patroni manages on its own node:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
    - install_etcd
    - install_patroni
    - install_backrest
    - role: install_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
    - setup_etcd
    - setup_patroni
    - role: setup_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
    - setup_backrest
```

The `haproxy` play needs no change. `setup_haproxy` emits the pooled listener
by itself in any zone that has a pooled node, and emits nothing extra in a zone
that has none.

After deployment, each zone's HAProxy node offers both endpoints. Clients
choose which one they want:

```bash
# Direct connection to the zone's current primary
psql -h 192.168.6.16 -p 5432 -U admin demo

# Pooled connection through the primary's pgBouncer
psql -h 192.168.6.16 -p 6432 -U admin demo
```

Two properties of that split are worth knowing before clients are pointed at
it. The endpoints enforce separate client authentication rules, so a client
that reaches one is not automatically admitted to the other, and nothing fails
a pooled connection over to PostgreSQL: a dead pooler on the leader is an
outage of the pooled endpoint alone. And Spock replication always uses the
direct listener, so cross-zone replication is unaffected by pooling or by a
pooler failure.

Because the pooled listener is TCP passthrough, the pooler sees the proxy's
address rather than the client's, and its own rules admit every role from that
address. Restrict access to `pooler_port` at the proxy or in the network. See
[Pooling Configuration](configuration/pooling.md) for the pool mode, TLS,
authentication and sizing parameters, and
[Proxy Configuration](configuration/proxy.md) for the port model and the
connection budget.
