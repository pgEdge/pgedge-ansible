# setup_coldfront_db

The `setup_coldfront_db` role creates the role, database and extensions
ColdFront needs on a pgEdge Distributed Postgres node, where
`coldfront_enabled` is set. It runs after Postgres is configured and
before `setup_pgedge`, so that in mesh mode the extensions exist before
the database joins Spock.

The role performs the following tasks on inventory hosts:

- Ask Postgres whether this node is a standby and which libraries it has
  loaded, retrying while a replica is still coming up.
- Check that Postgres has loaded `pg_duckdb` and `coldfront`, and stop
  with the reason if it has not.
- Create `coldfront_duckdb_role`, the NOLOGIN role `pg_duckdb` gates
  DuckDB execution on.
- Create `coldfront_db`, the database ColdFront's tiered storage lives in.
- Create the `pg_duckdb` and `coldfront` extensions in `coldfront_db`,
  with `dblink` as well in mesh mode.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_coldfront` installs the ColdFront packages.
- `setup_postgres`, or `setup_patroni` on an HA cluster, writes
  ColdFront's libraries and settings into the Postgres configuration and
  restarts Postgres to load them.

## When to Use

Execute this role on the `pgedge` group where `coldfront_enabled` is set,
after `setup_postgres` on a simple cluster or `setup_patroni` on an HA
cluster, and before `setup_pgedge`.

In the following example, the playbook creates ColdFront's objects on a
simple cluster:

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

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `coldfront_duckdb_role` | NOLOGIN role `pg_duckdb` gates DuckDB execution on. |
| `coldfront_db` | Database ColdFront's tiered storage lives in. |
| `coldfront_mesh` | Whether to create the `dblink` extension the bakery uses. |
| `pg_port` | Port the role connects to Postgres on. |

See the [ColdFront Configuration](../configuration/coldfront.md) reference
for descriptions and defaults.

## How It Works

### Loaded libraries

Creating ColdFront's extensions needs its libraries loaded, and Postgres
loads them only when it starts. `setup_postgres` and `setup_patroni`
restart Postgres to load them only where `pg_allow_restart` allows. Where
a restart was held back, the role stops before `CREATE EXTENSION` and says
so; restart Postgres, then run the role again.

### Mesh mode

In mesh mode `coldfront_db` is one of `db_names`, which `setup_pgedge`
puts into Spock. Spock replicates a `CREATE EXTENSION` issued once a
database has a Spock node to the other nodes, which create the extension
themselves, so the role creates every extension before `setup_pgedge`
runs, as upstream's mesh setup does.

### Under HA

The role runs on each zone's leader only, and the replicas receive its
results through physical replication. After a failover the leader need
not be `first_node_in_zone`, so each node asks its own Postgres whether
it is a standby.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role,
database and extensions are created only where they do not exist, and the
role writes no configuration and restarts nothing.
