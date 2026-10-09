# ColdFront Configuration

ColdFront is an optional tiered-storage add-on for a pgEdge Distributed
Postgres node: recent data stays in native Postgres partitions, older data
archives to Apache Iceberg on S3-compatible storage, and both are readable
and writable through the same SQL. It depends on Lakekeeper, the Iceberg
REST catalog every cold-tier commit goes through, and an S3-compatible
object store behind that catalog. The `install_coldfront` and
`setup_coldfront` roles configure the add-on itself; `install_lakekeeper`
and `setup_lakekeeper` build the catalog as a separate, dedicated host.

The `sample-playbooks/simple-cluster-coldfront` playbook runs all four in
order: a play for the `lakekeeper` group first, then the `pgedge` play,
with `install_coldfront` and `setup_coldfront` after `setup_pgedge`.

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
  `lakekeeper_port`, or Lakekeeper exits at startup.

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
- Description: Password for `lakekeeper_db_user`.

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
- Description: Full URL of the object store. Left empty, AWS's own
  endpoint resolution is used instead of a custom one.

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
- Description: Access key for the object store.

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

The following parameters are specific to `install_coldfront` and
`setup_coldfront`.

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
  storage lives in, separate from whatever general-purpose databases the
  cluster already lists in `db_names`.

### coldfront_supported_pg_versions

- Type: List
- Default: `[16, 17, 18]`
- Description: Postgres major versions ColdFront packages are published
  for. `install_coldfront` asserts `pg_version` is one of these before
  installing anything, rather than letting an unsupported version fail
  with an opaque package-manager error.

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
written from one node only. Setting this to `true` is not yet validated
against a live multi-zone cluster.

## Shared Preload Libraries

### pgedge_preload_libraries

- Type: List
- Default: `[spock, snowflake, pg_stat_statements]`
- Description: Base `shared_preload_libraries` list for a pgEdge
  Distributed Postgres node. `setup_postgres` templates
  `shared_preload_libraries` from this list rather than a literal
  string, so `setup_coldfront` can append `pg_duckdb` and `coldfront` to
  it instead of overwriting Spock and Snowflake.

## Object Store

This collection does not deploy an object store. Point the parameters
above at an S3-compatible store that is already available.
