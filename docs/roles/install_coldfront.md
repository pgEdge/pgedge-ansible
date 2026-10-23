# install_coldfront

The `install_coldfront` role installs the ColdFront tiered-storage
extension onto an existing pgEdge Distributed Postgres node, rather than
standing up a separate instance. ColdFront keeps recent data in native
Postgres partitions and archives older data to Iceberg on S3-compatible
storage, readable and writable through the same SQL with no application
changes.

The role performs the following tasks on inventory hosts:

- Install the ColdFront Postgres extension package, the `pgedge-coldfront`
  package holding the archiver, partitioner and compactor, and
  `pgedge-python3-psycopg2`.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` refuses a `pg_version` ColdFront packages are not
  published for, before anything is installed.
- `install_pgedge` installs the base Postgres package this role's package
  depends on.

## When to Use

ColdFront is opt-in per cluster, through `coldfront_enabled` on the
`pgedge` group. Add this role to the `pgedge` play of a cluster playbook,
after `install_pgedge` and before `setup_postgres`. `setup_postgres` then
preloads ColdFront's libraries, and Postgres will not start with a library
it cannot find. Follow `setup_postgres` with `setup_coldfront_db`, and
`setup_pgedge` with `setup_coldfront`.

In the following example, the playbook installs and sets up ColdFront only
where `coldfront_enabled` is set:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
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

ColdFront also needs Lakekeeper (`install_lakekeeper` and
`setup_lakekeeper`) serving before `setup_coldfront` runs, and an
S3-compatible object store reachable from this host. The
`sample-playbooks/simple-cluster-coldfront` playbook sets up Lakekeeper in a play of
its own ahead of this one, for the `lakekeeper` group. See the
[ColdFront Configuration](../configuration/coldfront.md) reference for the
settings both need.

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_version` | Names the ColdFront extension package to install. |

The settings ColdFront runs on once installed, such as its database and
its DuckDB role, belong to
[setup_coldfront](setup_coldfront.md#configuration).

See the [Configuration Reference](../configuration.md) and
[ColdFront Configuration](../configuration/coldfront.md) for descriptions
and defaults.

## How It Works

### Supported releases

ColdFront packages exist for Postgres 16, 17, and 18, confirmed against the
package lists on `apt.pgedge.com` and `dnf.pgedge.com`. They are listed in
`coldfront_supported_pg_versions`, and `init_server` refuses
`coldfront_enabled` with any other `pg_version`, before anything is
installed, rather than letting this role fail with an opaque
package-manager error.

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
