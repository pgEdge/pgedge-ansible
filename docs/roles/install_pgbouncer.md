# install_pgbouncer

The `install_pgbouncer` role installs pgBouncer, the connection pooler that
serves the optional pooled endpoint in front of each pgEdge node. The role
installs the package only; the `setup_pgbouncer` role writes the
configuration and starts the service.

The role performs the following task on inventory hosts:

- Install the pgBouncer package from the pgEdge repository.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables to the role.

Run `install_repos` before this role so the pgEdge repository is available.

## When to Use

Pooling is opt-in by inventory group. Execute this role on the hosts in the
`pgbouncer` group, which must be a subset of the `pgedge` group, after
`install_repos` and before `setup_pgbouncer`.

In the following example, the playbook installs pgBouncer on the pooled
nodes only:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
    - role: install_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
```

## Configuration

This role uses the following parameter from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pgbouncer_package` | Name of the pgBouncer package to install (default: `pgedge-pgbouncer`). |

See the [Pooling Configuration](../configuration/pooling.md) document for the
full set of pooling parameters.

## How It Works

The role installs pgBouncer from the pgEdge package repository and leaves it
unconfigured.

1. Install `pgbouncer_package` using the system package manager (APT or DNF),
   refreshing the package cache first.
2. Retry up to five times with twenty-second delays and a 300-second package
   lock timeout, matching the other install roles.

The collection requires pgBouncer 1.21 or later, which is where
`max_prepared_statements` arrived. Without that parameter, transaction pooling
breaks every client that uses protocol-level prepared statements. The pgEdge
repository currently ships 1.25.1 on both platforms.

## Usage Examples

In the following example, the playbook installs pgBouncer with the default
package name:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role: install_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
```

In the following example, the playbook installs a specific pgBouncer build:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pgbouncer_package: pgedge-pgbouncer-1.25.1
  roles:
    - role: install_pgbouncer
      when: inventory_hostname in (groups['pgbouncer'] | default([]))
```

Both examples run the play against the whole `pgedge` group and gate the role
on group membership rather than targeting `hosts: pgbouncer` directly. The
`setup_pgbouncer` role requires that form, so the sample playbooks use it for
both roles.

## Artifacts

This role installs a package rather than generating files. The package
provides the following:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `pgbouncer` binary | New | Installed to `/usr/bin` on RHEL-based systems and `/usr/sbin` on Debian-based systems. |
| `pgbouncer.service` | New | Systemd service unit shipped by the package. |
| `/etc/pgbouncer/pgbouncer.ini` | New | Packaged default configuration, replaced by `setup_pgbouncer`. |

## Platform-Specific Behavior

On RHEL-based systems, the package creates a dedicated `pgbouncer` system user
and group, owns `/var/log/pgbouncer` and `/run/pgbouncer`, ships its own
logrotate rule, and leaves the service disabled and stopped.

On Debian-based systems, the package creates no `pgbouncer` user, because its
unit runs as `postgres`. It logs beside PostgreSQL in `/var/log/postgresql`,
where the `pgedge-postgresql-common` logrotate glob already covers it. Its
`postinst` enables and starts `pgbouncer.service` against the packaged
configuration,
which binds `localhost:6432` with an empty userlist, so nothing can
authenticate through it until `setup_pgbouncer` runs. The package also ships a
`pgbouncer.socket` unit, disabled, which `setup_pgbouncer` masks.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The package
manager reports no change when the package is already present.

!!! info "The Package Is Already There"
    `pgedge-enterprise-all` depends on `pgedge-pgbouncer`, so the package is
    installed on every pgEdge node whether or not the node joined the
    `pgbouncer` group. Membership in that group gates the configuration and
    the running service, not the installation.
