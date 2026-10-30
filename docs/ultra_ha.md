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
    backup_repo_cipher: "{{ vault_backup_repo_cipher }}"

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

`backup_repo_cipher` is the password PgBackRest encrypts the repository with.
It has no default and the deployment refuses to run without one, so it is
given here as a vaulted variable alongside the other secrets. It belongs under
`all` rather than under `pgedge`: the backup servers render the same repository
configuration as the nodes they serve and have to arrive at the same value. Set
`backup_repo_cipher_type: none` instead where the storage layer encrypts — an
S3 bucket with default encryption, for example — and leave the cipher unset.

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
    - install_etcd
    - install_patroni
    - install_backrest
    - setup_backrest
    - setup_postgres
    - setup_etcd
    - setup_patroni

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

- hosts: pgedge:backup

  collections:
    - pgedge.platform

  roles:
    - finalize_backrest
```

HAProxy must be configured before `setup_pgedge` runs so that Spock
subscriptions target the proxy layer. This ensures subscriptions survive a
Patroni failover without requiring manual resubscription.

`setup_backrest` runs before `setup_postgres` because Patroni's configuration
carries the pgBackRest archive command, so Postgres starts archiving as soon as
Patroni starts it, and because `setup_postgres` asks the repository whether it
already holds this cluster before initializing a data directory.
`finalize_backrest` runs last because creating the repository stanza and taking
the first backup need a cluster that is already up. It takes a backup only when
the repository holds no backup that can restore the cluster running now, so
re-running this playbook against an existing cluster leaves the repository's
recovery point where it is.

## Running the Playbook

Run the playbook with the following command, substituting your inventory file
path:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```


## Adding a Backup Configuration

By default, backups use SSH to transmit data to the dedicated backup server in
each zone. To use AWS S3 instead, update your configuration, setting
`backup_repo_type` to `s3` and supplying the required parameters. An S3 zone
has no backup server: remove the hosts from the `backup` group and drop the
`hosts: backup` play, because `init_server` refuses an S3 zone that still has
one.

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
is opt-in and cluster-wide, like `is_ha_cluster`: set `pgbouncer_enabled` on the
`pgedge` group and every node runs a pooler in front of its own PostgreSQL.

It is cluster-wide by design. The pooled HAProxy listener health-checks
Patroni's leader endpoint, exactly as the direct listener does, so it routes
only to the pooler on the current leader — and any node of the zone can become
that leader. A zone that pooled only some of its nodes would lose the pooled
endpoint on the first failover to one of the others, which is why `init_server`
rejects an inventory whose nodes disagree.

Add the setting to the inventory:

```yaml
pgedge:
  vars:
    pgbouncer_enabled: true
    pgbouncer_auth_password: "{{ vault_pgbouncer_auth_password }}"
  # ... hosts as above ...
```

`pgbouncer_auth_password` is the pooler's own PostgreSQL login, the one
password the collection writes to disk. The playbook refuses to run while it is
still the default.

Then add the two pooling roles to the `pgedge` play, gated on
`pgbouncer_enabled`. `install_pgbouncer` goes with the other install roles, and
`setup_pgbouncer` after `setup_patroni`, because the pooler forwards to the
PostgreSQL instance Patroni manages on its own node:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_pgedge
    - install_etcd
    - install_patroni
    - install_backrest
    - role: install_pgbouncer
      when: pgbouncer_enabled | bool
    - setup_backrest
    - setup_postgres
    - setup_etcd
    - setup_patroni
    - role: setup_pgbouncer
      when: pgbouncer_enabled | bool
```

The `haproxy` play needs no change. `setup_haproxy` emits the pooled listener
by itself wherever the cluster pools, with every node of the zone behind it, and
emits nothing extra where it does not.

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

## Adding ColdFront Tiered Storage

ColdFront keeps recent data in native Postgres partitions and archives older
data to Apache Iceberg on S3-compatible storage, readable and writable through
the same SQL. On an Ultra-HA cluster it runs in mesh mode, which orders
cold-tier commits across the zones, and `init_server` refuses ColdFront on an
HA cluster without it. Mesh mode needs the ColdFront database in `db_names`,
so that `setup_pgedge` puts it into Spock with the cluster's other databases.
ColdFront is optional, so it has a sample playbook and inventory of its own,
in `sample-playbooks/ultra-ha-coldfront`, beside the plain `ultra-ha` ones.

Add the settings to the inventory, with the host that serves the Lakekeeper
Iceberg catalog in a `lakekeeper` group of its own. The collection deploys no
object store, so point the `coldfront_s3_*` settings at one that already
exists, with its bucket created:

```yaml
all:
  vars:
    lakekeeper_host: 192.168.6.20
    coldfront_s3_endpoint: https://s3.example.com
    coldfront_s3_bucket: iceberg
    coldfront_s3_access_key: "{{ vault_s3_access_key }}"
    coldfront_s3_secret_key: "{{ vault_s3_secret_key }}"

pgedge:
  vars:
    coldfront_enabled: true
    coldfront_mesh: true
    db_names:
      - demo
      - coldfront
  # ... hosts as above ...

lakekeeper:
  vars:
    lakekeeper_db_password: "{{ vault_lakekeeper_db_password }}"
  hosts:
    192.168.6.20:
```

Both groups read the catalog and object store settings, so they go under
`all`. For AWS S3, leave `coldfront_s3_endpoint` empty, set
`coldfront_s3_region`, and set `coldfront_s3_path_style` to `false`.

Then add a play for the Lakekeeper host after `init_server`, since
`setup_coldfront` fails if the catalog is not already serving, and the three
ColdFront roles. `install_coldfront` goes with
the other install roles, before `setup_postgres`, which preloads ColdFront's
libraries, and on every member, replicas included. `setup_coldfront_db`
follows `setup_patroni`, to create ColdFront's database and extensions on
each zone's leader before `setup_pgedge` puts the database into Spock.
`setup_coldfront` comes after `setup_pgedge`, since in mesh mode it adds
ColdFront's tables to Spock's replication set:

```yaml
- hosts: lakekeeper

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_lakekeeper
    - setup_lakekeeper

- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_pgedge
    - install_etcd
    - install_patroni
    - install_backrest
    - install_coldfront
    - setup_backrest
    - setup_postgres
    - setup_etcd
    - setup_patroni
    - setup_coldfront_db

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
    - setup_coldfront
```

The `sample-playbooks/ultra-ha-coldfront` playbook includes both. See
[ColdFront Configuration](configuration/coldfront.md) for the catalog, object
store and ColdFront parameters, and the
[setup_coldfront](roles/setup_coldfront.md#under-ha) role page for how
ColdFront runs on each zone's leader and replicas.

## Adding the AI DBA Workbench

The pgEdge AI DBA Workbench monitors every member of every zone, raises alerts,
and with a language model configured adds AI-assisted analysis. It is
optional, so it has a sample playbook and inventory of its own, in
`sample-playbooks/ultra-ha-ai-dba-workbench`, beside the plain `ultra-ha`
ones. Put one host in an `ai_dba_workbench` group of its own. That host runs
the Workbench's server, collector, alerter and web client, and keeps the
Workbench's datastore in a Postgres instance of its own, so it cannot be a
pgEdge node as well. The Workbench's server package depends on a
documentation knowledge base of about 2.6 GB, so the host needs the disk for
it, except on Ubuntu 26.04, where the package does not depend on it.

Add the Workbench host and its passwords to the inventory:

```yaml
all:
  vars:
    ai_dba_workbench_monitor_password: "{{ vault_ai_dba_workbench_monitor_password }}"

ai_dba_workbench:
  vars:
    ai_dba_workbench_db_password: "{{ vault_ai_dba_workbench_db_password }}"
    ai_dba_workbench_admin_password: "{{ vault_ai_dba_workbench_admin_password }}"
  hosts:
    192.168.6.21:
```

Both groups read `ai_dba_workbench_monitor_password`, so it goes under `all`:
`setup_ai_dba_workbench_monitor` creates the role the Workbench logs in to
every member as, and `setup_ai_dba_workbench` gives the Workbench its
password.
`ai_dba_workbench_admin_password` must be at least 12 characters long.

Patroni's configuration admits the Workbench host. Add
`setup_ai_dba_workbench_monitor` after `setup_pgedge`, in the same play, where
it installs the `system_stats` package on every member, and creates the
monitoring role and the extensions on each zone's leader, which reach the
replicas through physical replication. Then add a play for the Workbench host
at the end of the playbook, since `setup_ai_dba_workbench` registers every
member with the Workbench. `init_server` has already run on it, in the first
play:

```yaml
- hosts: pgedge

  collections:
    - pgedge.platform

  roles:
    - setup_pgedge
    - setup_ai_dba_workbench_monitor

- hosts: ai_dba_workbench

  collections:
    - pgedge.platform

  roles:
    - install_repos
    - install_ai_dba_workbench
    - setup_ai_dba_workbench
```

Each member is registered directly on its own Postgres port, rather than
through HAProxy, so the Workbench sees every member and works out each zone's
replication topology itself. The `sample-playbooks/ultra-ha-ai-dba-workbench`
playbook includes both. When it has finished, open
`https://192.168.6.21:8444` in a browser and sign in as `admin` with
`ai_dba_workbench_admin_password`.

Without a language model, the Workbench monitors the members and raises
alerts, and its AI features are off. See
[AI DBA Workbench Configuration](configuration/ai_dba_workbench.md) for the
model settings and every other parameter.
