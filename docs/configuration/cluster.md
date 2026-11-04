# Cluster Configuration

The collection uses cluster-wide configuration variables across multiple roles.
These settings define the basic operation, identity, and user accounts for the
cluster.

## cluster_name

- Type: String
- Default: `demo`
- Description: This parameter specifies the canonical name for the cluster.
  The collection uses this name for descriptive items and generated values
  such as stanza names and etcd key prefixes.

In the following example, the inventory specifies a production cluster name:

```yaml
cluster_name: production-cluster
```

## zone

- Type: Integer
- Default: `1`
- Description: This parameter specifies the zone or region identifier for a
  node. The zone serves two purposes: organizing nodes into logical groups and
  providing the Snowflake sequence ID. In simple clusters, use one node per
  zone. In HA clusters, assign multiple nodes to the same zone to form a
  Patroni cluster.

In the following example, the inventory assigns each node to a separate zone:

```yaml
hosts:
  node1.example.com:
    zone: 1
  node2.example.com:
    zone: 2
```

## repo_name

- Type: String
- Default: `release`
- Options: `release`, `staging`, `daily`
- Description: This parameter controls which pgEdge repository tier to use
  for software installation. Contact the pgEdge team before using `staging`
  or `daily` in production environments.

In the following example, the inventory uses the release repository:

```yaml
repo_name: release
```

## repo_prefix

- Type: String
- Default: (none)
- Description: This parameter enables installation of specific custom or
  automated builds. Contact pgEdge staff for valid values.

## repo_url

- Type: String
- Default: (none)
- Description: This parameter names a package repository of your own, such
  as a mirror or a caching proxy, for the `install_repos` role to use in place
  of the pgEdge repository servers. When this parameter is empty, the role
  installs the `pgedge-release` package, which points the host at the pgEdge
  servers. When the parameter is set, the role removes that package and writes
  the equivalent repository definition, pointing at this URL instead. The URL
  must begin with `http://`, `https://`, or `file:///`.

In the following example, the inventory points RHEL hosts at a caching proxy
of `dnf.pgedge.com` and Debian hosts at a proxy of `apt.pgedge.com`:

```yaml
rhel_hosts:
  vars:
    repo_url: https://artifacts.example.com/pgedge-dnf
debian_hosts:
  vars:
    repo_url: https://artifacts.example.com/pgedge-apt
```

## repo_layout

- Type: String
- Default: `upstream`
- Options: `upstream`, `mirror`
- Description: This parameter describes how the repository at `repo_url`
  arranges its contents. The `upstream` layout matches the pgEdge servers
  themselves, which is the arrangement a caching proxy or a copy of a
  repository server keeps. In this layout, `repo_url` replaces
  `https://dnf.pgedge.com` on RHEL hosts or `https://apt.pgedge.com` on Debian
  hosts, and `repo_name` selects the tier as usual. The `mirror` layout matches
  a mirror built by a proposed pgEdge mirror procedure, which keeps every
  platform under one URL and mirrors only the `release` tier.

In the following example, the inventory points every host at a pgEdge mirror,
whatever the operating system:

```yaml
repo_url: http://mirror.example.com/pgedge
repo_layout: mirror
```

## repo_gpg_key

- Type: String
- Default: (none)
- Description: This parameter specifies the URL of the key that signs pgEdge
  packages. When this parameter is empty, the `install_repos` role fetches the
  key from where the layout keeps the key under `repo_url`, so a host on an
  isolated network needs no access to the pgEdge servers. The role always
  checks package signatures. Use this parameter only together with `repo_url`.

In the following example, the inventory fetches the key from an internal
server:

```yaml
repo_url: https://artifacts.example.com/pgedge-dnf
repo_gpg_key: https://keys.example.com/pgedge-rsa.pub
```

## db_names

- Type: List
- Default: `[demo]`
- Description: This parameter specifies the database names for the Spock
  cluster. At least one name is required. The roles create any missing
  databases automatically and install the Spock and Snowflake extensions in
  each. Every pgEdge node must list the same databases, in any order, since
  Spock replicates each one between all of them; set it on the `pgedge`
  group. `init_server` refuses an inventory whose nodes disagree.

In the following example, the inventory specifies multiple database names:

```yaml
db_names:
  - app_db
  - reporting_db
```

### Removing a database from db_names

Removing a name from `db_names` does not drop the database. It tells the
collection to stop managing it, and the database stays exactly as it is on
every node: its data, its Spock node, its subscriptions and their replication
slots.

!!! warning "Retire the database before you remove its name"
    Removing the name also removes the `pg_hba.conf` rules that let the nodes
    connect to the database as `pgedge_user`, and Spock needs those
    connections to take the database apart. `spock.sub_drop` connects to the
    provider to drop the subscription's replication slot there; once the
    provider refuses that connection, the slot stays behind, and
    `DROP DATABASE` then fails because a replication slot still exists in
    the database. A database whose name is removed first can be left
    partially dismantled, with slots that only manual cleanup removes.

    Follow [Retiring a database](#retiring-a-database) while the name is
    still in `db_names`, and remove the name as the last step.

From the next run on, the collection no longer does any of the following for
the database:

- Admits it in `pg_hba.conf`, for the `pgedge_user` and `db_user` connections
  between nodes. Connections already open carry on, but any that reconnects is
  refused. That includes every other zone's Spock subscription, so replication
  of the database stops at the next restart, failover or network interruption.
- Admits it in pgBouncer's client authentication rules, where pgBouncer is
  enabled.
- Creates it, or the Spock and Snowflake extensions in it, on any node.
- Creates its Spock node or its subscriptions to the other zones, or repairs
  any that are missing.
- Cleans its Spock metadata and seeds it to the other zones during a recovery
  with `recover_postgres`.

The collection still backs the database up, since pgBackRest backs up the
whole cluster. It also never shrinks the worker and replication slot pools on
its own, so removing the name cannot keep Postgres or Spock from starting. It
does stop counting the database, though, so a database added to `db_names`
later takes the room the removed one still uses. List a database you keep in
[unmanaged_db_names](#unmanaged_db_names) so that the pools grow for both. See
[Worker and Replication Sizing](postgres.md#worker-and-replication-sizing).

#### Retiring a database

Take the database apart in this order, while its name is still in `db_names`:

1. Stop every application that writes to the database.
2. On every zone's primary, connect to the database and drop each of its
   subscriptions with `spock.sub_drop`. Each call reaches the provider zone to
   drop the matching replication slot there, which works only while the
   provider still admits `pgedge_user`.
3. On every zone's primary, confirm that `pg_replication_slots` shows no slot
   left for the database. A slot that remains means a `spock.sub_drop` call
   could not reach its provider; resolve that before going on.
4. Remove the name from `db_names`.
5. Drop the database on every zone's primary. Replicas in an Ultra-HA zone
   follow their primary.
6. Run the deployment playbook. It removes the database's `pg_hba.conf` and
   pgBouncer rules. The worker and replication slot pools stay at their
   current size; to bring them down, set them in `pg_parameters`, as
   [Worker and Replication Sizing](postgres.md#worker-and-replication-sizing)
   describes.

Do not run the playbook between dropping the database and removing its name:
while the name is in `db_names`, a run creates the database again, empty, and
subscribes it to the other zones.

#### Reopening access to a removed database

If the name is already gone from `db_names` and the database is not, use
`custom_hba_rules` to admit `pgedge_user` to it again, then follow
[Retiring a database](#retiring-a-database) from step 2. The same rules also
keep the database replicating when you mean to take it over and manage it
yourself, rather than retire it. In that case, also add its name to
[unmanaged_db_names](#unmanaged_db_names), so that the worker and replication
slot pools keep counting its subscriptions.

Each rule must admit the address that Spock connections to the database come
from: every pgEdge node, and on Ultra-HA, every proxy the subscriptions
connect through. A single rule whose `source` covers the cluster's network
does both. In the following example, the inventory admits `pgedge_user`, here
the default `pgedge`, to the removed `reporting_db` database from the
cluster's network:

```yaml
custom_hba_rules:
  - contype: host
    users: pgedge
    databases: reporting_db
    source: 10.0.0.0/24
```

Run the deployment playbook to apply the rule, which reloads Postgres or
Patroni on each node. Do not add the name back to `db_names` instead: the
next run would create the subscriptions the retirement has already dropped.
Once the database is dropped, remove the rule and run the playbook again.

## unmanaged_db_names

- Type: List
- Default: `[]`
- Description: This parameter lists databases that the collection does not
  manage but that the worker and replication slot pools must still be sized
  for. The collection does not create, admit, replicate or retire them; it
  only counts them in
  [Worker and Replication Sizing](postgres.md#worker-and-replication-sizing).
  A name may not appear in both `unmanaged_db_names` and `db_names`, or name
  a database the collection creates for a component it sets up, such as
  `coldfront_db`, which the sizing already counts. Like `db_names`, it must
  be the same on every pgEdge node, since every node's pools are sized for
  every database; set it on the `pgedge` group.

The collection cannot see what a database it does not manage holds, so it
counts each one listed as though it replicates to every other zone, the same as
a database in `db_names`. A database that does not replicate needs fewer
workers and slots than that, and the difference is a few spare of each.

List a database here when the cluster runs one that `db_names` does not name:

- A database removed from `db_names` that you keep replicating yourself, as
  [Reopening access to a removed
  database](#reopening-access-to-a-removed-database) describes. Move the name
  from `db_names` to `unmanaged_db_names` in the same change, and add the
  `custom_hba_rules` that keep it reachable.
- A database created by hand on the cluster's nodes, replicated or not. Spock
  starts a manager worker in every database that accepts connections.

Remove the name once the database is dropped. The pools do not shrink on their
own when you do; see
[Worker and Replication Sizing](postgres.md#worker-and-replication-sizing).

In the following example, the inventory keeps `reporting_db`, taken over from
`db_names`, counted alongside the databases the collection manages:

```yaml
db_names:
  - app_db
unmanaged_db_names:
  - reporting_db
```

## db_user

- Type: String
- Default: `admin`
- Description: This parameter specifies the primary database username. This
  username must differ from the OS user running Ansible.

In the following example, the inventory specifies a custom database user:

```yaml
db_user: appuser
```

## db_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the database user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
db_password: "{{ vault_db_password }}"
```

## pgedge_user

- Type: String
- Default: `pgedge`
- Description: This parameter specifies the database username for pgEdge
  inter-node logical replication. The cluster uses this account for Spock
  operations between nodes.

## pgedge_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the pgEdge
  replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
pgedge_password: "{{ vault_pgedge_password }}"
```

## is_ha_cluster

- Type: Boolean
- Default: `false`
- Description: This parameter enables high availability features. When `true`,
  the collection installs and configures etcd, Patroni, and HAProxy on the
  appropriate nodes.

In the following example, the inventory enables high availability mode:

```yaml
is_ha_cluster: true
```

## replication_user

- Type: String
- Default: `replicator`
- Description: This parameter specifies the username for Patroni streaming
  replication. This setting only applies to HA clusters.

## replication_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the Patroni
  replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
replication_password: "{{ vault_replication_password }}"
```

## synchronous_mode

- Type: Boolean
- Default: `false`
- Description: This parameter enables Patroni management of `synchronous_commit`
  and `synchronous_standby_names` based on cluster state.

## synchronous_mode_strict

- Type: Boolean
- Default: `false`
- Description: This parameter enforces synchronous commit when `synchronous_mode`
  is enabled, even if no synchronous replicas are available. Enabling this
  setting can prevent writes during replica failures.

!!! warning "Data Availability Trade-off"
    Strict synchronous mode prioritizes data durability over availability.
    The cluster blocks writes if synchronous replicas become unavailable.

## tls_validity_days

- Type: Integer
- Default: `3560`
- Description: This parameter controls the validity period in days for TLS
  certificates generated by the collection. The default of approximately ten
  years avoids cluster disruptions due to certificate expiration.

In the following example, the inventory sets a one-year certificate validity:

```yaml
tls_validity_days: 365
```

## spock_version

- Type: String
- Default: `5.0.4`
- Description: This parameter specifies the minimum version of the Spock
  extension to install. The latest available version is always installed.

!!! warning "Security"
    Never commit passwords to version control. Use Ansible Vault or environment
    variables for any `_password` parameters.
