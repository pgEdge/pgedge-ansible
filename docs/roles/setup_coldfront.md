# setup_coldfront

The `setup_coldfront` role creates the additional database ColdFront's
tiered storage lives in, installs the ColdFront extensions there, and points
them at the Lakekeeper catalog and the S3-compatible object store behind it.
Postgres itself is configured for ColdFront by `setup_postgres`, where
`coldfront_enabled` is set.

The role performs the following tasks on inventory hosts:

- Check that the object store and the Lakekeeper catalog are reachable
  from this host, since both are used at query time, not just at setup
  time.
- Check that Postgres has loaded the `pg_duckdb` and `coldfront`
  libraries, and stop before changing anything if it has not.
- Create the `coldfront_duckdb_role` NOLOGIN role and the `coldfront_db`
  database.
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
  Postgres node this role installs into. `setup_postgres` also writes
  ColdFront's libraries and settings into its configuration.

## When to Use

Execute this role after `setup_pgedge`, with `install_coldfront` placed
before `setup_postgres` and `coldfront_enabled` set on the `pgedge` group:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_pgedge
    - install_coldfront
    - setup_postgres
    - setup_pgedge
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
| `coldfront_enabled` | Must be set, so that `setup_postgres` has loaded ColdFront's libraries. |
| `coldfront_duckdb_role` | NOLOGIN role `pg_duckdb` gates DuckDB execution on. |
| `coldfront_db` | Name of the additional database ColdFront's tiered storage lives in. |
| `lakekeeper_host` / `lakekeeper_port` / `lakekeeper_warehouse` | Locates the Iceberg catalog this node writes through. |
| `coldfront_s3_*` | Locates and authenticates to the S3-compatible object store. |
| `coldfront_mesh` | Whether cold-tier commits are coordinated between nodes (see below). Defaults to `false`. |
| `pg_parameters` | Any `shared_preload_libraries` it names stay loaded beside ColdFront's. |
| `db_user` / `db_password` | The cluster's existing admin user, reused as the archiver's, partitioner's and compactor's database identity rather than a bespoke role. |

See the [ColdFront Configuration](../configuration/coldfront.md) reference
for descriptions and defaults.

## How It Works

### Postgres configuration

ColdFront's libraries and settings are part of the Postgres configuration
`setup_postgres` writes where `coldfront_enabled` is set, the same way as
the rest of the collection's parameters. `pg_duckdb` and `coldfront` join
`shared_preload_libraries` after the collection's own libraries and
before any that `pg_parameters` names, so enabling ColdFront never
disables Spock replication. ColdFront's settings are parameters the
collection controls, so `init_server` refuses `pg_parameters` that sets
any of them. See
[pg_parameters](../configuration/postgres.md#pg_parameters).

`setup_postgres` restarts Postgres to load the libraries the way it
applies any parameter that needs a restart: one node at a time, and only
where `pg_allow_restart` allows. This role checks that they have loaded
before it creates anything, since the extensions cannot be created until
they have.

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
role, and extension creation are all no-ops once already done. The role
writes no Postgres configuration and restarts nothing; `setup_postgres`
does both.
