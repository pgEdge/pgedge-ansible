# setup_coldfront

The `setup_coldfront` role points the ColdFront extensions at the
Lakekeeper catalog and the S3-compatible object store behind it, and
configures the archiver, partitioner and compactor. Postgres itself is
configured for ColdFront by `setup_postgres`, and ColdFront's role, database
and extensions are created by
[`setup_coldfront_db`](setup_coldfront_db.md), where `coldfront_enabled` is
set. In mesh
mode the role also has ColdFront order cold-tier commits across the nodes of
the Spock cluster. It works on HA clusters too, in mesh mode; see
[Under HA](#under-ha).

The role performs the following tasks on inventory hosts:

- Check that the object store and the Lakekeeper catalog are reachable
  from this host, since both are used at query time, not just at setup
  time.
- In mesh mode, add ColdFront's bakery and catalog tables to Spock's
  `default` replication set.
- Call `coldfront.set_storage_secret()` with the configured object-store
  credentials, region, URL style and SSL setting, an idempotent upsert
  run on every pass, on every node or, in mesh mode, on the first. With
  `coldfront_s3_endpoint` empty the endpoint is passed as `NULL`, which
  ColdFront documents as the setting for AWS S3. The task's output is
  hidden, since the query carries the secret.
- Write the archiver, partitioner, and compactor configuration to
  `/etc/pgedge/coldfront/config.yaml`, leaving it out of `--diff` output
  since it holds credentials.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_coldfront` installs the ColdFront packages.
- `setup_postgres` and `setup_pgedge` bring up the pgEdge Distributed
  Postgres node this role configures. `setup_postgres` also writes
  ColdFront's libraries and settings into its configuration wherever
  `coldfront_enabled` is set.
- `setup_coldfront_db` creates ColdFront's role, database and extensions.

## When to Use

ColdFront is opt-in per cluster, through `coldfront_enabled` on the
`pgedge` group. Execute this role after `setup_pgedge`, with
`install_coldfront` placed before `setup_postgres` and `setup_coldfront_db`
between `setup_postgres` and `setup_pgedge`.

In the following example, the playbook sets ColdFront up only where
`coldfront_enabled` is set:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_pgedge
    - role: install_coldfront
      when: coldfront_enabled | bool
    - setup_postgres
    - role: setup_coldfront_db
      when: coldfront_enabled | bool
    - setup_pgedge
    - role: setup_coldfront
      when: coldfront_enabled | bool
```

The role checks the Lakekeeper catalog's `/health` endpoint before
changing anything, and fails if the catalog has not answered within about
30 seconds. Run `setup_lakekeeper` in an earlier play, as the
`sample-playbooks/simple-cluster-coldfront` and
`sample-playbooks/ultra-ha-coldfront` playbooks do.

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `coldfront_enabled` | Gates the role. Where it is set, `setup_postgres` has loaded ColdFront's libraries and `setup_coldfront_db` has created its extensions. |
| `coldfront_db` | Name of the additional database ColdFront's tiered storage lives in. |
| `lakekeeper_host` / `lakekeeper_port` / `lakekeeper_warehouse` | Locates the Iceberg catalog this node writes through. |
| `coldfront_s3_*` | Locates and authenticates to the S3-compatible object store. |
| `coldfront_mesh` | Whether cold-tier commits are ordered across nodes (see below). Defaults to `false`. |
| `db_names` | In mesh mode, must list `coldfront_db`, which puts it into Spock. |
| `pg_parameters` | Any `shared_preload_libraries` it names stay loaded beside ColdFront's. |
| `db_user` / `db_password` | The cluster's existing admin user, reused as the archiver's, partitioner's and compactor's database identity rather than a bespoke role. |
| `is_ha_cluster` | Whether the role's SQL runs on each zone's leader only (see [Under HA](#under-ha)). |
| `proxy_node` / `proxy_port` | Under HA, the endpoint the archiver, partitioner and compactor connect through. |

See the [ColdFront Configuration](../configuration/coldfront.md) reference
for descriptions and defaults.

## How It Works

### Postgres configuration

ColdFront's libraries and settings are part of the Postgres configuration
`setup_postgres` writes where `coldfront_enabled` is set, the same way as
the rest of the collection's parameters. `pg_duckdb` and `coldfront` join
`shared_preload_libraries` after the collection's own libraries and
before any that `pg_parameters` names, so enabling ColdFront never
disables Spock replication. The settings ColdFront depends on are
parameters the collection controls, so `init_server` refuses
`pg_parameters` that sets any of them; its tuning settings are defaults
`pg_parameters` may override. See
[pg_parameters](../configuration/postgres.md#pg_parameters) and
[Tuning](../configuration/coldfront.md#tuning).

`setup_postgres` restarts Postgres to load the libraries the way it
applies any parameter that needs a restart: one node at a time, and only
where `pg_allow_restart` allows. `setup_coldfront_db` then checks that
they have loaded before it creates ColdFront's role, database and
extensions, since the extensions cannot be created until they have.

### Database connections

ColdFront's backend opens two connections back into Postgres itself:
`coldfront.local_pg_dsn`, the `pglocal` attachment that streams Postgres
rows into Iceberg, and, in mesh mode, `coldfront.dblink_self`. Both run
as the `postgres` OS user over the Unix socket on `pg_port`, so both
connect as the `postgres` role, the only one peer authentication admits
there. Both name `coldfront_db`, because `postgresql.conf` applies them
to every database; another database that uses ColdFront needs its own
`local_pg_dsn`, for example, with the default `pg_port`:

```sql
ALTER DATABASE dbt7 SET coldfront.local_pg_dsn =
    'host=/var/run/postgresql port=5432 dbname=dbt7 user=postgres';
```

The archiver, partitioner and compactor run as the `coldfront` OS user,
which the ColdFront package creates, and connect as `db_user` over TCP
to `127.0.0.1`, where `pg_hba.conf` checks `db_password`. Under HA they
connect to the zone's endpoint instead, as [Under HA](#under-ha) explains.

### Vanilla and mesh modes

ColdFront upstream distinguishes a single-node "vanilla" mode, without
Spock or Snowflake, from an N-node Spock "mesh" mode that orders cold-tier
commits with the Ricart-Agrawala protocol, which ColdFront calls its
bakery. The extension uses the bakery only when both `snowflake.node` and
`coldfront.dblink_self` are set. Otherwise it serializes cold-tier commits
with an advisory lock local to the node, as in vanilla mode.

`coldfront_mesh: false`, the default, leaves `coldfront.dblink_self`
unset, so each node serializes only its own cold-tier commits, and nothing
orders commits between nodes. On a cluster of more than one node, write
each Iceberg table from one node only. ColdFront's
`_exec_iceberg_with_claim()` notes that when two commits to one table
race, duckdb-iceberg does not rebase the losing commit, and its data is
silently dropped.

`coldfront_mesh: true` arms the bakery, following upstream's mesh setup:

- `coldfront_db` must be listed in `db_names`, and `init_server` refuses
  mesh mode if it is not. `setup_postgres` then creates the database with
  the `spock` and `snowflake` extensions, and `setup_pgedge` gives it the
  same Spock nodes and subscriptions as the cluster's other databases.
  `snowflake.node` is already set to each node's `zone`.
- `setup_postgres` writes `coldfront.dblink_self`,
  `coldfront.peer_alive_window_ms` and `wal_receiver_status_interval` with
  ColdFront's other settings. `setup_coldfront_db` creates the `dblink`
  extension, which the bakery's claim and release go through, with
  ColdFront's other extensions. It creates them before `setup_pgedge` puts
  the database into Spock, as
  upstream's mesh setup does, because Spock replicates a `CREATE EXTENSION`
  issued once a database has a Spock node to the other nodes, which create
  the extension themselves.
- After `setup_pgedge`, it adds `coldfront.claims` and
  `coldfront.claim_acks`, through ColdFront's own
  `_ensure_claims_replicated()`, and `coldfront.storage_secret`,
  `coldfront.partition_config`, `coldfront.tiered_views` and
  `coldfront.archive_watermark` to Spock's `default` replication set.
  `coldfront.deferred_acks` stays local, as upstream intends.

The bakery treats a peer whose `pg_stat_replication.reply_time` is older
than `coldfront.peer_alive_window_ms` as dead and stops waiting for its
acknowledgement. `wal_receiver_status_interval` is set to one second so
that an idle peer still reports progress well inside that window. The same
rule means that during a network partition both sides can write the same
table, and upstream's mitigation is to fence the losing side.

In mesh mode only the first pgEdge host calls
`coldfront.set_storage_secret()`. `coldfront.storage_secret` replicates,
and ColdFront's trigger on it, which ColdFront enables for Spock's apply as
well, materializes the DuckDB secret on each node the row reaches. A call
on every node would have Spock record the identical updates as conflicts on
every run.

Upstream runs the archiver on one node only. This role writes
`config.yaml` on every node and schedules none of the tools, so run the
archiver on a single node.

### Under HA

On an HA cluster ColdFront's libraries and settings reach every member
through the zone's Patroni configuration, which `setup_patroni` keeps up
to date with the rest of the Postgres parameters, restarting the members
that need it. Every member, replicas included, needs the ColdFront
packages by then, so run `install_coldfront` on every node first.

`setup_coldfront_db` runs after `setup_patroni` and creates ColdFront's
role, database and extensions on each zone's leader, and the replicas
receive them through physical replication. Turning ColdFront on for a
running HA cluster needs no extra step, since `setup_patroni` restarts the
members to load the libraries, where `pg_allow_restart` allows, before
`setup_coldfront_db` runs.

Under HA the role:

- Requires `coldfront_mesh: true`, which `init_server` checks. The
  archiver, partitioner and compactor connect through the zone's
  endpoint, and Patroni's `pg_hba` admits `db_user` through the zone's
  proxies only to the databases in `db_names`.
- Asks each node's Postgres whether it is a standby, since after a
  failover the leader is not necessarily `first_node_in_zone`. The role's
  SQL runs on the leader only, and the replicas receive its results
  through physical replication.
- Has each replica write its own DuckDB secret from the replicated
  `coldfront.storage_secret` row, with
  `coldfront.materialize_storage_secret()`. Physical replication carries
  the row but not the secret, which DuckDB keeps in a file of its own and
  ColdFront's trigger writes only where the row is written, or applied
  by Spock.
- Points the archiver, partitioner and compactor at the zone's endpoint,
  the one `setup_pgedge` subscribes through: `proxy_node` if set,
  otherwise the zone's first HAProxy host, on `proxy_port`, otherwise the
  zone's first node. A replica's own Postgres is a read-only standby.

A replica serves cold-tier reads, and ColdFront refuses cold-tier writes
on a standby. Patroni is configured to leave Spock's logical slots alone,
so how Spock replication resumes after a zone fails over is decided by
Spock and the Ultra-HA design, not by ColdFront. Until it resumes, the
bakery in the other zones treats the failed-over zone as dead after
`coldfront.peer_alive_window_ms` and carries on.

### DuckDB extension loading

`duckdb.autoinstall_known_extensions` is set to `false`, per the
`pgedge-coldfront-duckdb-extensions` package's own shipped sample config
(`coldfront-duckdb-extensions.conf.sample`). With it `true`, a missing
extension file makes DuckDB silently fetch the unpatched upstream build,
which 409s under concurrency and writes manifests strict Iceberg readers
reject.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/pgedge/coldfront/config.yaml` | New | Archiver, partitioner, and compactor configuration: the Postgres DSN, the Iceberg catalog endpoint, and the S3 connection. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The
object-store credential is an upsert, the configuration file is rewritten
only when its content changes, and the mesh mode's replication-set
additions check membership first. The role creates no roles, databases or
extensions, writes no Postgres configuration and restarts nothing;
`setup_coldfront_db` does the first, and `setup_postgres` or
`setup_patroni` the other two.
