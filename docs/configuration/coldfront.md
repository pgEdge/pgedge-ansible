# ColdFront Configuration

ColdFront is an optional tiered-storage add-on for a pgEdge Distributed
Postgres node: recent data stays in native Postgres partitions, older data
archives to Apache Iceberg on S3-compatible storage, and both are readable
and writable through the same SQL. It depends on Lakekeeper, the Iceberg
REST catalog every cold-tier commit goes through, and an S3-compatible
object store behind that catalog. The `install_coldfront`,
`setup_coldfront_db` and `setup_coldfront` roles configure the add-on
itself; `install_lakekeeper` and `setup_lakekeeper` build the catalog as a
separate, dedicated host.

ColdFront is optional, so its sample playbooks and inventories are kept
apart from the plain ones. The `sample-playbooks/simple-cluster-coldfront`
playbook runs all five: a play for the `lakekeeper` group first, then the
`pgedge` play, with `install_coldfront` before `setup_postgres`,
`setup_coldfront_db` after it, and `setup_coldfront` after `setup_pgedge`.
The `sample-playbooks/ultra-ha-coldfront` playbook does the same on an
Ultra-HA cluster, in mesh mode, with `setup_coldfront_db` after
`setup_patroni`.

The simple-cluster and Ultra-HA end-to-end tests cover ColdFront with a
Lakekeeper host and SeaweedFS standing in for the object store. To run that
variant locally, pass `coldfront` after the operating system:

```bash
./tests/run-test.sh simple-cluster debian12 coldfront
./tests/run-test.sh ultra-ha debian12 coldfront
```

Add `mesh` as well to run the simple cluster's ColdFront in mesh mode. The
Ultra-HA test always runs it in mesh mode.

## Lakekeeper Parameters

The following parameters locate the Iceberg catalog and are read by both
`setup_coldfront`, which writes to it, and `setup_lakekeeper`, which
builds it. Set them once, in a scope both host groups can see.

### lakekeeper_host

- Type: String
- Default: (none)
- Description: Address the Lakekeeper catalog is reached at.

### lakekeeper_bind_ip

- Type: String
- Default: `{{ lakekeeper_host }}`
- Description: Address the Lakekeeper service itself binds.

### lakekeeper_port

- Type: Integer
- Default: `8181`
- Description: Port the Iceberg REST catalog and management API listen on.

### lakekeeper_metrics_port

- Type: Integer
- Default: `9000`
- Description: Port for Lakekeeper's Prometheus metrics. Must differ from
  `lakekeeper_port` and `pg_port`, or Lakekeeper exits at startup;
  `init_server` refuses ports that collide on the Lakekeeper host. On that
  host, `pg_port` is the port the catalog's own Postgres instance listens
  on, at the loopback address only.

### lakekeeper_warehouse

- Type: String
- Default: `wh`
- Description: Name of the Iceberg warehouse ColdFront writes through.

### lakekeeper_db

- Type: String
- Default: `lakekeeper`
- Description: Name of Lakekeeper's own catalog database.

### lakekeeper_db_user

- Type: String
- Default: `lakekeeper`
- Description: Database role that owns the catalog database.

### lakekeeper_db_password

- Type: String
- Default: `secret`
- Description: Password for `lakekeeper_db_user`. `init_server` refuses to
  run while it is still the default, so set it on the `lakekeeper` group,
  from Ansible Vault like the other passwords.

### lakekeeper_pg_data

- Type: String
- Default: `{{ pg_home }}/{{ pg_version }}/lakekeeper`
- Description: Data directory of the catalog's own Postgres instance,
  which `setup_lakekeeper` creates and runs as the `lakekeeper-postgres`
  service.

### lakekeeper_namespace

- Type: String
- Default: `public`
- Description: Iceberg namespace pre-created in the warehouse. Decoupled
  (Iceberg-only) tables need this namespace to exist in its own committed
  call, because `coldfront.create_iceberg_table()` defers the Iceberg
  `CREATE SCHEMA` to commit but posts the `CREATE TABLE` eagerly.

```yaml
all:
  vars:
    lakekeeper_host: 192.168.1.20
```

## Object Store Parameters

ColdFront's cold tier writes to any S3-compatible object store — real AWS
S3, MinIO, or a self-hosted store — not specifically any one product.
Both `setup_coldfront` (the archiver's own connection) and
`setup_lakekeeper` (the warehouse's storage credential, which Lakekeeper
uses to prove access by writing to the bucket) read these.

### coldfront_s3_endpoint

- Type: String
- Default: `""`
- Description: Full URL of the object store, `http(s)://host[:port]`.
  Left empty, AWS's own endpoint resolution is used instead of a custom
  one. `init_server` refuses any other form.

```yaml
coldfront_s3_endpoint: "http://192.168.1.10:8333"
```

### coldfront_s3_region

- Type: String
- Default: `us-east-1`
- Description: Region passed to the object store.

### coldfront_s3_bucket

- Type: String
- Default: `iceberg`
- Description: Bucket the cold tier's Parquet data and Iceberg metadata
  live in.

### coldfront_s3_access_key

- Type: String
- Default: `""`
- Description: Access key for the object store. Required: `init_server`
  refuses an empty value, as it does for the secret key, the bucket and
  the region.

### coldfront_s3_secret_key

- Type: String
- Default: `""`
- Description: Secret key for the object store.

In the following example, the inventory retrieves the credentials from
Ansible Vault:

```yaml
coldfront_s3_access_key: "{{ vault_s3_access_key }}"
coldfront_s3_secret_key: "{{ vault_s3_secret_key }}"
```

### coldfront_s3_path_style

- Type: Boolean
- Default: `true`
- Description: Whether to use path-style addressing, typical for
  self-hosted S3-compatible stores. Set to `false` for virtual-hosted-style
  addressing, typical for AWS S3.

## ColdFront Parameters

The following parameters control ColdFront on the pgEdge nodes.
`setup_postgres` (or `setup_patroni` on an HA cluster) reads them as well
as the ColdFront roles, since ColdFront's settings are among the Postgres
parameters it writes. `setup_coldfront_db` creates ColdFront's role,
database and extensions.

### coldfront_enabled

- Type: Boolean
- Default: `false`
- Description: Whether the pgEdge nodes run ColdFront. Set it on the
  `pgedge` group. `setup_postgres` then adds `pg_duckdb` and `coldfront`
  to `shared_preload_libraries`, after the collection's own libraries and
  before any that `pg_parameters` names, and writes ColdFront's settings
  with the rest of the Postgres configuration. The settings ColdFront
  depends on are parameters the collection controls, so `init_server`
  refuses `pg_parameters` that sets them; its tuning settings are defaults
  `pg_parameters` may override (see [Tuning](#tuning)). `init_server` also
  refuses `coldfront_enabled` on an HA cluster without `coldfront_mesh`,
  without `lakekeeper_host` or complete `coldfront_s3_*` settings, or with
  a `pg_version` outside `coldfront_supported_pg_versions`.
  `install_coldfront` has to run before `setup_postgres`, which restarts
  Postgres to load the libraries, one node at a time, unless
  `pg_allow_restart` is `false`. `setup_coldfront_db` then creates
  `coldfront_duckdb_role`, `coldfront_db` and the `pg_duckdb` and
  `coldfront` extensions. The sample playbooks run the ColdFront roles only
  where `coldfront_enabled` is set.

### coldfront_duckdb_role

- Type: String
- Default: `coldfront_duckdb`
- Description: NOLOGIN role `pg_duckdb` gates DuckDB execution on.
  Superusers always qualify; members reach the cold tier without
  superuser via `coldfront.grant_app_access()`.

### coldfront_db

- Type: String
- Default: `coldfront`
- Description: Name of the additional database ColdFront's tiered
  storage lives in. Outside mesh mode it stays separate from the
  general-purpose databases the cluster lists in `db_names`; mesh mode
  needs it listed there, which puts it into Spock.

### coldfront_supported_pg_versions

- Type: List
- Default: `[16, 17, 18]`
- Description: Postgres major versions ColdFront packages are published
  for. `init_server` refuses `coldfront_enabled` with any other
  `pg_version`, before anything is installed, rather than letting
  `install_coldfront` fail with an opaque package-manager error.

### coldfront_mesh

- Type: Boolean
- Default: `false`
- Description: Whether this node coordinates cold-tier commits with
  other nodes over Spock, rather than a local advisory lock. See below.

Upstream ColdFront distinguishes a single-node "vanilla" mode from an
N-node Spock "mesh" mode that coordinates cold-tier commits with the
Ricart-Agrawala protocol. `coldfront_mesh: false`, the default, leaves
`coldfront.dblink_self` unset, which keeps that protocol off even though
`setup_postgres` configures Spock and Snowflake on every pgEdge node. Each
node then serializes only its own cold-tier commits with a local advisory
lock, so on a cluster of more than one node each Iceberg table must be
written from one node only.

`coldfront_mesh: true` turns the protocol on, following upstream's mesh
setup. It needs `coldfront_db` listed in `db_names`, so that the database
joins Spock alongside the others, and `init_server` refuses it otherwise.
The [setup_coldfront](../roles/setup_coldfront.md) role page covers what
else it sets up. An HA cluster requires `true`, and `init_server` refuses
ColdFront there otherwise.

In the following example, the inventory turns mesh mode on for every
pgEdge node:

```yaml
pgedge:
  vars:
    coldfront_mesh: true
    db_names:
    - demo
    - coldfront
```

## Tuning

ColdFront's tuning settings are defaults, which
[pg_parameters](postgres.md#pg_parameters) may override like any other:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `coldfront.iceberg_async_parquet` | `on` | ColdFront's asynchronous Parquet writing, which the collection turns on. |
| `coldfront.peer_alive_window_ms` | `5000` | Mesh mode only. How long, in milliseconds, a peer may go without reporting replication progress before the bakery stops waiting for its acknowledgement and treats it as dead. Upstream's default. |
| `wal_receiver_status_interval` | `1s` | Mesh mode only. How often each node reports replication progress, so an idle peer stays inside the window above. |

Raise `coldfront.peer_alive_window_ms` on slow or lossy links between
nodes, where a live peer can otherwise be ruled dead. Keep
`wal_receiver_status_interval` well inside it, or every idle peer looks
dead to the bakery.

```yaml
pgedge:
  vars:
    pg_parameters:
      coldfront.peer_alive_window_ms: 10000
```

## Object Store

This collection does not deploy an object store. Point the parameters
above at an S3-compatible store that is already available.
