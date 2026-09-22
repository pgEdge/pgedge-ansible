# install_coldfront

The `install_coldfront` role installs the ColdFront tiered-storage
extension onto an existing pgEdge Distributed Postgres node, rather than
standing up a separate instance. ColdFront keeps recent data in native
Postgres partitions and archives older data to Iceberg on S3-compatible
storage, readable and writable through the same SQL with no application
changes.

The role performs the following tasks on inventory hosts:

- Assert that `pg_version` is one ColdFront packages are actually
  published for.
- Install the ColdFront Postgres extension package, the `pgedge-coldfront`
  archiver/partitioner/compactor, `pgedge-python3-psycopg2`, and `acl`.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_pgedge` installs the base Postgres package this role's package
  depends on.
- `setup_postgres` initializes the Postgres instance ColdFront installs
  into.

## When to Use

Add this role to the `pgedge` play of a cluster playbook, after
`setup_pgedge`, and follow it with `setup_coldfront`:

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
    - install_coldfront
    - setup_coldfront
```

ColdFront also needs Lakekeeper (`install_lakekeeper`/`setup_lakekeeper`)
serving before `setup_coldfront` runs, and an S3-compatible object store
reachable from this host. The `sample-playbooks/simple-cluster-coldfront`
playbook sets up Lakekeeper in a play of its own ahead of this one. See
the [ColdFront Configuration](../configuration/coldfront.md) reference for
the settings both need.

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `coldfront_supported_pg_versions` | Postgres major versions ColdFront packages are published for. |
| `pg_version` | Checked against the list above before anything is installed. |

The settings ColdFront runs on once installed, such as its database and
its DuckDB role, belong to
[setup_coldfront](setup_coldfront.md#configuration).

See the [Configuration Reference](../configuration.md) and
[ColdFront Configuration](../configuration/coldfront.md) for descriptions
and defaults.

## How It Works

### Version checking, not comparison

`install_coldfront` asserts `pg_version` is in
`coldfront_supported_pg_versions` before installing anything, rather than
letting an unsupported version fail with an opaque package-manager error.
Confirmed against the actual package lists on `apt.pgedge.com` and
`dnf.pgedge.com`: ColdFront packages exist for Postgres 16, 17, and 18.

### Package names differ by OS family

The Postgres extension package depends on the base Postgres package
`install_pgedge` already installed, plus `pg_duckdb` and the patched
DuckDB extensions, but its own name differs by OS family:

| OS Family | Package name |
|-----------|--------------|
| Debian | `pgedge-postgresql-<pg_version>-coldfront` |
| RHEL | `pgedge-coldfront_<pg_version>` |

Debian nests the version between `postgresql` and the extension name;
RHEL suffixes the version onto the extension name instead, and drops
`postgresql` from the name entirely. `pgedge-coldfront` (the archiver,
partitioner, and compactor) and `pgedge-coldfront-duckdb-extensions` (the
patched DuckDB extensions) share the same name on both OS families.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. Package
installation is a no-op once already done.
