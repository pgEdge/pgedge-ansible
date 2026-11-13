# setup_pgedge

The `setup_pgedge` role configures Spock logical replication to initialize a
multi-master Postgres cluster. The role establishes Spock nodes and
subscriptions between all applicable Postgres instances, enabling bidirectional
data synchronization across zones and nodes.

The role performs the following tasks on inventory hosts:

- Create a Spock node named `edge[ZONE]` with the appropriate connection string.
- Set the Spock exception behavior to the value of `exception_behaviour`.
- Set the Snowflake node ID to the zone number.
- Enable DDL replication via Spock.
- Subscribe the current node to every other zone in the cluster.
- Before creating anything, read every zone's Spock state and stop if a zone
  is not yet part of a cluster that already holds data.
- Join the zones named in `pgedge_join_zones` to a running cluster, copying
  its data into them.

In HA clusters, the role runs only on each zone's primary, which after a
failover is not the zone's first node.
Subscriptions target the HAProxy node in the remote zone when one is
available.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `setup_postgres` installs Postgres with the Spock extension.
- `setup_patroni` must be complete in HA clusters so Patroni manages the
  primary node.
- `setup_haproxy` must be complete in HA clusters so subscriptions target
  the proxy layer.

!!! info "Role Order"
    In HA clusters, execute this role after `setup_haproxy`. Spock
    subscriptions target HAProxy so that replication continues after a
    Patroni failover without requiring manual resubscription.

## When to Use

Execute this role on all pgedge hosts after Postgres setup to establish
multi-master replication.

In the following example, the playbook invokes the role for standalone nodes:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - setup_pgedge
```

For HA clusters, the following example invokes the role after HAProxy setup:

```yaml
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
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `db_names` | Databases to configure for Spock replication. |
| `pg_port` | Postgres port for direct node connections. |
| `zone` | Zone identifier for multi-zone deployments. |
| `pgedge_user` | pgEdge user for node-to-node communication. |
| `pgedge_password` | Password for the pgEdge user account. |
| `proxy_node` | Specific proxy hostname for HA deployments. |
| `proxy_port` | Proxy port for HA deployments (default: 5432). |
| `pgedge_join_zones` | Zones to join to a cluster that already holds data, passed with `-e` (default: none). |
| `pgedge_join_wait_minutes` | How long a join waits for each bookmark and new subscription (default: 30). |
| `pgedge_seed_zone` | For recovery only: the zone the other zones copy their data from (HA only). |
| `pgedge_seed_stall_minutes` | Give up on a seed or join copy after this long without progress (default: 15). |
| `pgedge_seed_max_hours` | Longest a seed or join copy may take (default: 24). |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults, and [Spock Configuration](../configuration/spock.md) for the
`pgedge_join_*` and `pgedge_seed_*` parameters.

## How It Works

The role first finds out what the cluster already is, then creates Spock
nodes and subscriptions based on whether the cluster uses HA mode, and last
joins any zone named in `pgedge_join_zones`.

### Classifying the Cluster

Before it creates anything, the role asks each zone's primary, for every
database in `db_names`, whether the zone has its Spock node there, whether the
database holds tables of its own, and which subscriptions it has. Nothing in
this step writes. A zone whose primary cannot be asked stops the run, since
taking it for an empty zone could treat a running cluster as a new one.

A database *holds data* when some zone has its node there and tables of its
own. In such a database:

- A zone without a node is not yet part of the cluster.
- A zone with a node whose database carries `pgedge.join_pending` set to its
  own number is partway through a join, whatever subscriptions it has.
- Otherwise the zones with a node are *members* when each subscribes to every
  other one, enabled or not. If one zone lacks some of those subscriptions
  and the rest are complete, that zone is partway through a join.
- Any other shape stops the run, listing the missing subscriptions.

A database that holds no data on any zone is not classified: every zone takes
the ordinary path. This is also how a first deployment that failed partway
resumes.

The ordinary path never creates a node or subscription for a zone outside the
cluster in a database that holds data. Subscriptions are recognized by the
node they come from as well as by name, so the role never creates a second
subscription from the same zone.

### Gating

The result decides whether the run may go on:

- Without `pgedge_join_zones`, a zone that is not yet part of a cluster that
  holds data stops the run before anything is created in Spock. The message
  names the zone and the flag to pass.
- With `pgedge_join_zones`, the run stops when no database holds data (there
  is no cluster to join), when a zone that is not yet a member is missing
  from the list, when a listed zone is not in the inventory, or when
  `db_names` holds a database that no zone has in Spock yet. A listed zone
  that is already a member is reported and skipped.
- `pgedge_join_zones` and `pgedge_seed_zone` together stop the run. With
  `pgedge_seed_zone` alone, as in a recovery, the gate does not apply.

See
[Why an Ordinary Run Refuses a New Zone](../add_zone.md#why-an-ordinary-run-refuses-a-new-zone).

### Standalone Deployment

When `is_ha_cluster` is `false`, the role creates direct node-to-node
connections. It creates a Spock node named `edge{{ zone }}` on each node and
subscribes each node to every other node, resulting in a full mesh topology
where all nodes replicate to all other nodes.

### HA Deployment

When `is_ha_cluster` is `true`, the role creates zone-based connections
through HAProxy. It creates Spock nodes only on each zone's primary, as
[Zone Primary](role_config.md#zone-primary) finds it, and subscribes each zone
to every other zone. A database added to `db_names` on a running cluster gets
its Spock node and subscriptions the same way. The subscription connection
target is selected in the following priority order:

1. The `proxy_node` variable, if set.
2. The first HAProxy node in the remote zone.
3. The first pgEdge node in the remote zone, as a fallback.

The `proxy_port` parameter controls the port used for these connections,
allowing HAProxy to run on a pgEdge node rather than a dedicated host.

### Subscription Synchronization

After creating subscriptions, the role waits for initial synchronization
using the `spock.sub_wait_for_sync()` function. These subscriptions copy
nothing, so the wait is short; only the copy from a seed zone, described
below, takes time in proportion to the database's size.

### Joining a Zone to a Running Cluster

Once the rest of the cluster is wired together, the role joins each zone in
`pgedge_join_zones`, one at a time in the order given, and each zone's
databases one at a time in `db_names` order. It follows Spock's own
zero-downtime add-node procedure, written as separate tasks so that each step
can be checked, resumed and reported on its own. The joining zone is N, the
zone it copies from is the source S (the lowest-numbered member), and the
other members are Z.

First, a set of checks that change nothing:

- Spock is 5.0.9 or later in every database on every zone, and N's Spock is
  no older than any member's in its major and minor release. Patch releases
  are not compared.
- N has the `lolor` extension wherever S replicates `lolor` tables.
- Every zone runs with worker, slot, WAL sender and replication origin pools
  at least as large as the larger cluster needs, with no restart pending.
- Every subscription among the members is enabled and `replicating`, waiting
  up to five minutes for the apply workers the run restarted.
- No member still subscribes to N in a database where N has no node yet, as
  the members do when N was a member before and was rebuilt without
  `remove_zone`.
- N's databases hold nothing a join would not have created.

Then, for each database:

1. Copy S's roles to N with `pg_dumpall --roles-only` piped into `psql`,
   skipping roles N already has. Once per zone. The password hashes are never
   written to disk.
2. Create N's Spock node.
3. On each Z, create the replication slot N's subscription from Z will read,
   and on N, that subscription, disabled.
4. Set a bookmark on each Z and wait for S to apply it.
5. Where there is a Z, pause S's apply workers and record how far S has
   applied each Z. Then create N's subscription from S with `synchronize_structure` and
   `synchronize_data`. Wait for the copy, the same way a seed copy is waited
   for.
6. Set a bookmark on S and wait for N to apply it.
7. Advance each Z slot, and N's replication origin for it, to the last Z
   write N's copy holds. This runs only while N's subscription from Z is
   still disabled.
8. Add S's replication sets and their tables to N where N lacks them,
   reporting any difference left. Then enable N's subscriptions from each Z,
   and wait for N to apply a bookmark from each.
9. Subscribe S and every Z to N.
10. Exchange bookmarks between N and every member, and wait for every
    subscription both ways to be `replicating`.

Every bookmark is a `spock.sync_event()` waited for in `spock.progress`, for
up to `pgedge_join_wait_minutes`. On HA clusters every step runs on each
zone's primary.

Each step asks the cluster whether it is done, so a rerun after any failure
picks up where the last one stopped. The only thing stored is that a join has
not finished: before step 2, the role sets `pgedge.join_pending` to N on N's
database with `ALTER DATABASE`, and it resets the setting once step 10 has
passed. Classification takes a zone with a node and that setting for the zone
joining, even when every subscription already exists, so a join that stopped
in step 9 or 10 resumes too. The setting is in N's catalog, so N's replicas
have it, Spock does not replicate it to other zones, and it goes with the
database when `remove_zone` drops it. When a step
fails, the role sorts the failure into one of two kinds:

- **Resumable** (the default for anything unexpected): everything is kept,
  and the failure lists the slots the join holds on the other zones, the WAL
  each keeps, and how to drop them.
- **Not resumable**: the copy failed after it started, a slot N needs is gone,
  a slot cannot be placed, or N holds something the join did not create. The
  role drops N's subscriptions in that database and runs `remove_zone`'s
  `remaining_zones` task file to clear N from every other zone, then fails
  with the instruction to run [`remove_zone`](remove_zone.md) and join again.

See [Adding a Zone to a Running Cluster](../add_zone.md) for the procedure
from the operator's side.

### Seeding From One Zone

`pgedge_seed_zone` is for recovery only. To add a zone to a cluster that is
running, use `pgedge_join_zones`.

Every subscription the role creates normally copies nothing, because every
zone starts empty. When one zone already holds the cluster's data and the
others are empty and take no writes, set `pgedge_seed_zone` to that zone. Each other zone then
subscribes to the seed zone with `synchronize_structure` and
`synchronize_data`, and waits for the copy to finish, before the role creates
any other subscription. The recovery playbook uses this to refill the zones it
rebuilds from the zone it restored.

The wait for the copy does not use `spock.sub_wait_for_sync()`, which keeps
waiting while Spock restarts a copy that has failed. It polls
`spock.sub_show_status()` and `spock.local_sync_status` instead, and succeeds
once the subscription is `replicating` and every table is ready. It fails
immediately if the subscription is `disabled`. It also fails if the
subscription stays `down` for two minutes, as it does after a bad provider DSN
or password, or a copy that broke partway; Spock 5 does not resume a copy that
broke after it started. Last, it fails if nothing has moved for
`pgedge_seed_stall_minutes`. Movement is any change in the sync step, in the
tables left to sync, in the database's size, or in the progress Postgres reports
for the COPY and index builds. The failure message shows the subscription's
status, the tables not yet synced, and the Spock lines from the end of the
Postgres log. `pgedge_seed_max_hours` is a backstop for the whole wait. Each
database in `db_names` is waited for in turn, and both limits apply to each
database separately.

The copy runs once. A later run finds the subscription and leaves it alone, so
the setting does no harm if it stays in place.

!!! warning "Subscription Names"
    Subscription names follow the format `sub_n{{ zone }}_n{{ remote_zone }}`.
    Changing zone assignments after initial setup can cause subscription
    conflicts or render the cluster inoperable.

## Usage Examples

In the following example, the playbook deploys a standalone multi-master
cluster with two databases:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    db_names:
      - production
      - analytics
  roles:
    - setup_postgres
    - setup_pgedge
```

In the following example, the playbook specifies a custom proxy for
replication connections:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    is_ha_cluster: true
    proxy_node: "haproxy.example.com"
    proxy_port: 5000
  roles:
    - setup_pgedge
```

## Artifacts

This role modifies the following file and creates database objects on each
configured database:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `~postgres/.pgpass` | Modified | Password file entry for pgedge user authentication. |

The role also creates the following database objects in each configured
database:

| Object | Location | Purpose |
|--------|----------|---------|
| Spock nodes | `spock.node` table | Node metadata with node_id and node_name. |
| Spock subscriptions | `spock.subscription` table | Subscription metadata with sub_id and sub_name. |
| Replication slots | System catalog | Logical replication slots for each subscription. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role checks
whether Spock nodes and subscriptions exist before creating them.

!!! warning "Subscription Changes"
    Adding new zones or databases requires re-running this role on all nodes
    to establish the new subscriptions. A new zone in a cluster that holds
    data also needs `-e pgedge_join_zones`; see
    [Adding a Zone to a Running Cluster](../add_zone.md).
