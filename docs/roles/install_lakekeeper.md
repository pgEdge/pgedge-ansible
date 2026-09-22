# install_lakekeeper

The `install_lakekeeper` role installs Lakekeeper, the Iceberg REST catalog
that ColdFront's cold tier commits through, along with the Postgres packages
for the catalog's own instance, which `setup_lakekeeper` creates. Lakekeeper
is not a pgEdge Distributed Postgres node: its Postgres instance exists for
the catalog alone and never runs Spock.

The role performs the following tasks on inventory hosts:

- Install the `pgedge-lakekeeper` package, the Postgres packages for
  `pg_version`, and `pgedge-python3-psycopg2`.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares the host and checks the inventory, including
  that the host's ports do not collide.
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

Apply `init_server` to the Lakekeeper host first, as to every host. The
`sample-playbooks/simple-cluster` playbook does so in the same play:

```yaml
- hosts: lakekeeper
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    - install_lakekeeper
    - setup_lakekeeper
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_version` | Major version of the private Postgres instance installed here for the catalog. |

The settings the catalog itself runs on, such as its ports, its database
and its Iceberg namespace, belong to
[setup_lakekeeper](setup_lakekeeper.md#configuration).

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

1. Installs `pgedge-lakekeeper` and the Postgres package matching
   `pg_version`. Package names differ by OS family: Debian nests the
   version between `postgresql` and the package name
   (`pgedge-postgresql-<ver>`); RHEL suffixes the version onto the base
   name instead, and splits client tools (`pgedge-postgresql<ver>`) from
   the server binaries (`pgedge-postgresql<ver>-server`), both of which
   this role installs. On RHEL it also installs the contrib package, which
   holds the extensions Lakekeeper's migration needs.

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
installation is a no-op once already done.
