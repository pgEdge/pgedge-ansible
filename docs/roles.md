# Role Reference

This page describes each role in the pgEdge Ansible Collection and provides
links to detailed documentation for each role.

## Role Execution Order

Roles must be applied in a specific order to satisfy dependencies. The
following list shows the correct execution sequence:

1. [`init_server`](roles/init_server.md) - Prepares all servers in the
   cluster.
2. [`install_repos`](roles/install_repos.md) - Installs the pgEdge and PGDG
   package repositories.
3. [`install_pgedge`](roles/install_pgedge.md) - Installs pgEdge packages on
   pgEdge nodes.
4. [`install_etcd`](roles/install_etcd.md) - Installs etcd on pgEdge nodes
   (HA only).
5. [`install_patroni`](roles/install_patroni.md) - Installs Patroni on pgEdge
   nodes (HA only).
6. [`install_backrest`](roles/install_backrest.md) - Installs PgBackRest on
   backup-capable nodes.
7. [`install_pgbouncer`](roles/install_pgbouncer.md) - Installs pgBouncer on
   pgEdge nodes (pooled clusters only).
8. [`setup_backrest`](roles/setup_backrest.md) - Writes the PgBackRest
   configuration.
9. [`setup_postgres`](roles/setup_postgres.md) - Initializes PostgreSQL on
   pgEdge nodes.
10. [`setup_etcd`](roles/setup_etcd.md) - Configures and starts etcd (HA only).
11. [`setup_patroni`](roles/setup_patroni.md) - Configures Patroni and starts
    the HA cluster (HA only).
12. [`setup_pgbouncer`](roles/setup_pgbouncer.md) - Configures and starts
    pgBouncer on pooled nodes.
13. [`setup_haproxy`](roles/setup_haproxy.md) - Configures HAProxy on haproxy
    nodes (HA only).
14. [`setup_pgedge`](roles/setup_pgedge.md) - Creates Spock nodes and
    establishes subscriptions.
15. [`finalize_backrest`](roles/finalize_backrest.md) - Initializes the backup
    repository and schedules backups.

`setup_backrest` comes before `setup_postgres`, and therefore before
`setup_patroni`, for two reasons. An HA cluster gets its `archive_command` from
the Patroni configuration, so Postgres starts archiving the moment Patroni
starts it, and a `pgbackrest.conf` written later leaves a window in which every
archive attempt fails. And `setup_postgres` asks the repository whether it
already holds a cluster before it initializes a data directory, which it can
only do once `pgbackrest.conf` names the repository. Nothing `setup_backrest`
does touches Postgres, so it can sit that early.

That question matters when the only thing that survived an outage is the backup
repository. Deploying onto replacement hardware with the original inventory
would otherwise build an empty cluster whose system identifier does not match
the stanza — one that can never archive to its own repository, while appearing
healthy. `setup_postgres` refuses instead and points at the recovery playbook.
The check is skipped during a recovery, where an empty data directory beside a
full repository is exactly what was intended.

`finalize_backrest` is last because everything it does needs a cluster that is up
and wired together. It takes a full backup only when the repository has none, so
re-running a playbook against a cluster whose repository already holds backups
adds nothing to it — which matters, because the default retention would
otherwise expire the recovery point the repository already had.

The two pgBouncer roles are the only optional pair in the sequence. Pooling is
opt-in per cluster, so both are gated on `pgbouncer_enabled`; a cluster that
does not pool omits them and is otherwise unchanged. See
[Pooling Configuration](configuration/pooling.md).

[`recover_cluster`](roles/recover_cluster.md) is not part of this sequence. It
rebuilds an existing cluster from its backup repository and is applied by its own
playbook. See [Recovering a Cluster from Backup](recovery.md).

## Role Categories

The roles in this collection fall into five categories.

### Configuration Foundation

| Role | Description |
|------|-------------|
| [`role_config`](roles/role_config.md) | Provides shared variables and computed values to all other roles. You do not call this role directly. |

### Server Preparation

| Role | Description |
|------|-------------|
| [`init_server`](roles/init_server.md) | Initializes servers with required packages and system configuration. |
| [`install_repos`](roles/install_repos.md) | Configures the pgEdge and PGDG package repositories. |

### Software Installation

| Role | Description |
|------|-------------|
| [`install_pgedge`](roles/install_pgedge.md) | Installs Postgres with pgEdge extensions. |
| [`install_etcd`](roles/install_etcd.md) | Installs etcd for HA cluster coordination. |
| [`install_patroni`](roles/install_patroni.md) | Installs Patroni for HA management. |
| [`install_backrest`](roles/install_backrest.md) | Installs PgBackRest for backup and restore operations. |
| [`install_pgbouncer`](roles/install_pgbouncer.md) | Installs pgBouncer for connection pooling on pooled nodes. |

### Service Configuration

| Role | Description |
|------|-------------|
| [`setup_postgres`](roles/setup_postgres.md) | Initializes and configures Postgres instances. |
| [`setup_etcd`](roles/setup_etcd.md) | Configures and starts etcd clusters. |
| [`setup_patroni`](roles/setup_patroni.md) | Configures and starts Patroni. |
| [`setup_pgbouncer`](roles/setup_pgbouncer.md) | Configures and starts pgBouncer on pooled nodes. |
| [`setup_haproxy`](roles/setup_haproxy.md) | Installs and configures HAProxy. |
| [`setup_pgedge`](roles/setup_pgedge.md) | Establishes Spock replication between nodes. |
| [`setup_backrest`](roles/setup_backrest.md) | Writes the PgBackRest configuration. |
| [`finalize_backrest`](roles/finalize_backrest.md) | Initializes the backup repository and schedules backups. |

### Recovery

| Role | Description |
|------|-------------|
| [`recover_cluster`](roles/recover_cluster.md) | Rebuilds an existing cluster from its PgBackRest repository. Applied by its own playbook, not as part of a deployment. |
