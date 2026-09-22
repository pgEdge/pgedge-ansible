# setup_coldfront

The `setup_coldfront` role configures Postgres for the ColdFront extension,
creates the additional database ColdFront's tiered storage lives in, and
points it at the Lakekeeper catalog and the S3-compatible object store
behind it.

The role performs the following tasks on inventory hosts:

- Check that the object store and the Lakekeeper catalog are reachable
  from this host, since both are used at query time, not just at setup
  time.
- Create the `coldfront_duckdb_role` NOLOGIN role and the `coldfront_db`
  database.
- Append ColdFront's Postgres configuration — extending
  `shared_preload_libraries` rather than overwriting it — and restart
  Postgres only when that configuration actually changed.
- Create the `pg_duckdb` and `coldfront` extensions in `coldfront_db`.
- Call `coldfront.set_storage_secret()` with the configured object-store
  credentials, region, URL style and SSL setting, an idempotent upsert
  run on every pass. With `coldfront_s3_endpoint` empty the endpoint is
  passed as `NULL`, which ColdFront documents as the setting for AWS S3.
  The task's output is hidden, since the query carries the secret.
- Write the archiver, partitioner, and compactor configuration to
  `/etc/pgedge/coldfront/config.yaml`, leaving it out of `--diff` output
  since it holds credentials.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_coldfront` installs the ColdFront packages.
- `setup_postgres` and `setup_pgedge` bring up the pgEdge Distributed
  Postgres node this role installs into.

## When to Use

Execute this role immediately after `install_coldfront`:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_pgedge
    - install_coldfront
    - setup_coldfront
```

The role checks the Lakekeeper catalog's `/health` endpoint before
changing anything, and fails if the catalog has not answered within about
30 seconds. Run `setup_lakekeeper` in an earlier play, as the
`sample-playbooks/simple-cluster-coldfront` playbook does.

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `coldfront_duckdb_role` | NOLOGIN role `pg_duckdb` gates DuckDB execution on. |
| `coldfront_db` | Name of the additional database ColdFront's tiered storage lives in. |
| `lakekeeper_host` / `lakekeeper_port` / `lakekeeper_warehouse` | Locates the Iceberg catalog this node writes through. |
| `coldfront_s3_*` | Locates and authenticates to the S3-compatible object store. |
| `coldfront_mesh` | Whether cold-tier commits are coordinated between nodes (see below). Defaults to `false`. |
| `pgedge_preload_libraries` | The base `shared_preload_libraries` list this role extends rather than overwrites. |
| `db_user` / `db_password` | The cluster's existing admin user, reused as the archiver's, partitioner's and compactor's database identity rather than a bespoke role. |

See the [ColdFront Configuration](../configuration/coldfront.md) reference
for descriptions and defaults.

## How It Works

### Extending, not overwriting, shared_preload_libraries

This role appends its own `postgresql.conf` block after `setup_postgres`'s
own block, using a distinct marker so the two coexist, and computes
`shared_preload_libraries` as `pgedge_preload_libraries` (Spock, Snowflake,
and `pg_stat_statements` by default) plus `pg_duckdb` and `coldfront`, so
enabling ColdFront never silently disables Spock replication.

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
to `127.0.0.1`, where `pg_hba.conf` checks `db_password`.

### Vanilla and mesh modes

ColdFront upstream distinguishes a single-node "vanilla" mode, without
Spock or Snowflake, from an N-node Spock "mesh" mode that coordinates
cold-tier commits with the Ricart-Agrawala protocol. The extension uses
that protocol only when both `snowflake.node` and `coldfront.dblink_self`
are set. Otherwise it serializes cold-tier commits with an advisory lock
local to the node, as in vanilla mode.

`coldfront_mesh: false`, the default, leaves `coldfront.dblink_self`
unset, so each node serializes only its own cold-tier commits, and nothing
coordinates commits between nodes. On a cluster of more than one node,
write each Iceberg table from one node only. ColdFront's
`_exec_iceberg_with_claim()` notes that when two commits to one table
race, duckdb-iceberg does not rebase the losing commit, and its data is
silently dropped.

Setting `coldfront_mesh: true`, and everything a real multi-zone Spock mesh
needs beyond it, is follow-up work not yet validated against a live
multi-node cluster.

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

This role is idempotent and safe to re-run on inventory hosts. Database,
role, and extension creation are all no-ops once already done. The
Postgres configuration block only triggers a restart when its content
actually changes.
