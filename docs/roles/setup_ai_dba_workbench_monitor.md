# setup_ai_dba_workbench_monitor

The `setup_ai_dba_workbench_monitor` role prepares a pgEdge Distributed
Postgres node to be monitored by the pgEdge AI DBA Workbench, where the
inventory has an `ai_dba_workbench` host. It creates the role the Workbench
monitors the node as, the extensions its probes read and the grants it needs.
It runs once the nodes are built, after every role that creates a database the
Workbench reads, and before `setup_ai_dba_workbench` registers the nodes with
the Workbench.

The role performs the following tasks on inventory hosts:

- Stop unless the inventory has an `ai_dba_workbench` host.
- Install the `system_stats` extension's package.
- Ask Postgres whether this node is a standby, retrying while a replica is
  still coming up.
- Create `ai_dba_workbench_monitor_user` and grant it `pg_monitor`.
- Create the `pg_stat_statements` and `system_stats` extensions in `postgres`
  and every database the collection creates.
- Grant the role `monitor_system_stats`, read access to `pg_hba_file_rules`
  and `pg_ident_file_mappings`, and read access to Spock's status tables.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_repos` configures the pgEdge repository the `system_stats`
  package comes from.
- `setup_postgres` creates the databases in `db_names`, with the Spock
  extension in each, and on a simple cluster admits the Workbench host, which
  on an HA cluster `setup_patroni` does through Patroni's configuration.
  `setup_coldfront_db` creates `coldfront_db` where `coldfront_enabled` is
  set.

## When to Use

Execute this role on the `pgedge` group where the inventory has an
`ai_dba_workbench` host, after every role that creates a database the
Workbench reads, `setup_pgedge` among them, and before
`setup_ai_dba_workbench`. On an inventory without one the role stops. The
`sample-playbooks/simple-cluster-ai-dba-workbench` and
`sample-playbooks/ultra-ha-ai-dba-workbench` playbooks run it after
`setup_pgedge`, in the same play, ahead of the play for the Workbench host.

In the following example, the playbook builds and prepares the nodes, and then
builds the Workbench host:

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
    - setup_ai_dba_workbench_monitor

- hosts: ai_dba_workbench
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    - install_ai_dba_workbench
    - setup_ai_dba_workbench
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `ai_dba_workbench_monitor_user` | Role the Workbench logs in to every node as. |
| `ai_dba_workbench_monitor_password` | Password for `ai_dba_workbench_monitor_user`. Declared in `role_config`, and `init_server` refuses the default or an empty one. |
| `db_names` | Databases the extensions and grants are made in, Spock's among them. |
| `coldfront_enabled` | Whether `coldfront_db` is one of the databases the role prepares. |
| `coldfront_db` | ColdFront's database, where `coldfront_enabled` is set. |
| `pg_version` | Postgres major version the `system_stats` package is installed for. |
| `pg_port` | Port the role connects to Postgres on. |

See the [AI DBA Workbench Configuration](../configuration/ai_dba_workbench.md)
reference for descriptions and defaults.

## How It Works

### The monitoring role

The role creates:

- The role `ai_dba_workbench_monitor_user`, which can log in with
  `ai_dba_workbench_monitor_password`, and its membership in `pg_monitor`,
  which gives it the statistics views, every setting, and the query text in
  `pg_stat_statements`, without superuser.
- The `pg_stat_statements` and `system_stats` extensions in each database in
  `db_names`, `postgres`, and `coldfront_db` where `coldfront_enabled` is set.
  The collector reads `pg_stat_statements` in every database it visits, and
  `system_stats` in the database each node is registered with. It also visits
  a database created outside the collection, finds no `pg_stat_statements`
  there and skips that probe; the view in the databases above reports that
  database's statements too.
- Membership in `monitor_system_stats`, the role `system_stats` grants its
  functions to after revoking them from `PUBLIC`.
- `SELECT` on `pg_hba_file_rules` and `pg_ident_file_mappings`, and `EXECUTE`
  on the functions behind them, in each of those databases. Postgres restricts
  both views to superusers, and a grant on a system view applies only in the
  database it is made in.
- `USAGE` on the `spock` schema and `SELECT` on `spock.node`,
  `spock.local_node`, `spock.subscription`, `spock.exception_log` and
  `spock.resolutions` in each database in `db_names`, which the Workbench
  reads to place each node in the cluster's topology and to report
  replication errors.

The `system_stats` package is `pgedge-postgresql-<ver>-system-stats` on
Debian-based systems and `pgedge-system_stats_<ver>` on RHEL-based systems,
which the enterprise-all bundle does not include.

### Access from the Workbench host

The nodes admit the Workbench host as `ai_dba_workbench_monitor_user`, to
every database, with a `scram-sha-256` password. The rule is `role_config`'s
`pg_ai_dba_workbench_hba_rules`, which joins `pg_required_hba_rules`, the
rules `setup_postgres` writes on a simple cluster and `setup_patroni` writes
on an HA one. This role adds no rule of its own: `setup_postgres` writes a
simple cluster's `pg_hba.conf` anew on every run, so a rule added after it
would be gone from the file after any run of `setup_postgres` alone, and
refused from the node's next reload or restart.

### Spock

Every session the role opens sets `spock.enable_ddl_replication` to `off`,
through the `connect_params` option of the `community.postgresql` modules. By
the time the role runs, `setup_pgedge` has put each database in `db_names`
into Spock. Every node creates these objects itself, and a replicated copy of
each statement would arrive at nodes that already hold the object and fail
there as a Spock apply exception.

### Under HA

The role installs the package on every member, and creates the role, the
extensions and the grants on each zone's leader only. The replicas receive
those through physical replication. After a failover the leader need not be
`first_node_in_zone`, so each node asks its own Postgres whether it is a
standby.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The package,
the role, the extensions and the grants are created only where they do not
exist, and the role's password is set only where it differs from the
inventory's. The role writes no configuration and restarts nothing.
