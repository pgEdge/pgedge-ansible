# install_lakekeeper

The `install_lakekeeper` role installs Lakekeeper, the Iceberg REST catalog
that ColdFront's cold tier commits through, along with a private Postgres
instance for the catalog's own state. Lakekeeper is not a pgEdge Distributed
Postgres node: its Postgres instance exists for the catalog alone and never
runs Spock.

The role performs the following tasks on inventory hosts:

- Check that no other configured service on this host wants the same port
  as Lakekeeper or its metrics endpoint.
- Install the `pgedge-lakekeeper` package, the Postgres package for
  `pg_version`, `pgedge-python3-psycopg2`, and `acl`.
- Ensure a standalone Postgres cluster exists and is running, via
  `role_config`'s `ensure_postgres_cluster` task.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_repos` configures pgEdge package repositories.

## When to Use

Execute this role on a dedicated `lakekeeper` host, separate from any pgEdge
Distributed Postgres node. Lakekeeper's own architecture notes call for the
catalog to live on its own instance, "never co-located on a ColdFront data
node," since co-locating couples the catalog's availability and load to a
data node.

```yaml
- hosts: lakekeeper
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_lakekeeper
    - setup_lakekeeper
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `lakekeeper_port` | Port Lakekeeper's REST catalog and management API listen on. Checked here for collisions with the other services on this host. |
| `lakekeeper_metrics_port` | Port for Lakekeeper's Prometheus metrics endpoint. Must differ from `lakekeeper_port`, or Lakekeeper exits at startup. |
| `pg_version` | Major version of the private Postgres instance installed here for the catalog. |

Both ports are shared with `setup_lakekeeper` and so are declared in
`role_config`. The settings the catalog itself runs on, such as its
database and its Iceberg namespace, belong to
[setup_lakekeeper](setup_lakekeeper.md#configuration).

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

1. Asserts that `pg_port`, `lakekeeper_port`, and `lakekeeper_metrics_port`
   are all distinct. A SeaweedFS release from 4.x onward starts its own
   built-in Iceberg catalog on 8181 whenever its S3 gateway is enabled,
   which is Lakekeeper's default port too, so a genuine collision here is
   easy to hit by accident.
2. Installs `pgedge-lakekeeper` and the Postgres package matching
   `pg_version`. Package names differ by OS family: Debian nests the
   version between `postgresql` and the package name
   (`pgedge-postgresql-<ver>`); RHEL suffixes the version onto the base
   name instead, and splits client tools (`pgedge-postgresql<ver>`) from
   the server binaries (`pgedge-postgresql<ver>-server`), both of which
   this role installs.
3. Creates the Postgres cluster via `role_config`'s `ensure_postgres_cluster`
   task, since this is a standalone instance rather than a pgEdge
   Distributed Postgres node managed by `setup_postgres`.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/usr/bin/lakekeeper` | New | Lakekeeper's own binary. |

## Platform-Specific Behavior

Confirmed against the packaged file lists on `apt.pgedge.com` and
`dnf.pgedge.com`: on RHEL, the base `pgedge-postgresql<ver>` package is
client tools only (`psql`, `pg_dump`, and similar); the server binaries
(`postgres`, `initdb`, `pg_ctl`) live in the separate
`pgedge-postgresql<ver>-server` package, which this role also installs.
Debian's `pgedge-postgresql-<ver>` package is the server itself, with no
such split.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. Package
installation and cluster creation are both no-ops once already done.
