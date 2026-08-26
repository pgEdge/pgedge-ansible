# setup_pgbouncer

The `setup_pgbouncer` role configures and starts pgBouncer on each pooled
pgEdge node. The pooler listens on `pgbouncer_port` and forwards every
database to the node's own PostgreSQL instance on `127.0.0.1`, giving the node
a second endpoint that shares the cluster's roles and passwords but has its
own client authentication rules.

The role performs the following tasks on inventory hosts:

- Create `/etc/pgbouncer` owned by the platform's pgBouncer service user.
- Write a systemd drop-in that sets `Restart=always` and raises
  `LimitNOFILE` to match the configured connection ceiling.
- Write `userlist.txt` containing the pooler's own PostgreSQL login.
- Stage the TLS certificate and key the pooled endpoint presents to clients.
- Render the pooler's own `pg_hba.conf` from the cluster's HBA variables.
- Render `pgbouncer.ini`.
- Mask the packaged `pgbouncer.socket` unit on Debian-based systems.
- Start and enable the pgBouncer service, restarting it only when something it
  reads has changed.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables to the role.

The role also requires the following to have run already:

- `install_pgbouncer` installs the pgBouncer package.
- `setup_postgres` creates the pooler's PostgreSQL login and the
  `pgbouncer.get_auth` credential lookup that `auth_query` calls. Both are
  created wherever `pgbouncer_enabled` is set.

## When to Use

Execute this role on the pgEdge nodes after PostgreSQL is running: after
`setup_postgres` in a simple cluster, and after `setup_patroni` in a high
availability cluster. In an HA cluster the pooler forwards to the
node's local PostgreSQL whether that node is currently the primary or a
replica, and HAProxy decides which pooler receives traffic.

In the following example, the playbook configures the pooler only where the
cluster pools:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_postgres
    - role: setup_pgbouncer
      when: pgbouncer_enabled | bool
```

Run the play against the whole `pgedge` group and gate the role on
`pgbouncer_enabled`, as shown. The pooler's HBA template reads
`ansible_default_ipv4` out of `hostvars` for every pgEdge node and for the
zone's proxies, and a narrower play leaves those facts ungathered.

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pgbouncer_port` | Port the pooler listens on (default: 6432). Must differ from `pg_port`. |
| `pgbouncer_listen_addr` | Addresses the pooler binds (default: `*`). |
| `pgbouncer_auth_user` | PostgreSQL role the pooler logs in as to look up client credentials. |
| `pgbouncer_auth_password` | Password for `pgbouncer_auth_user`. Must be changed from the default. |
| `pgbouncer_pool_mode` | `session` or `transaction`. See [Pooling Configuration](../configuration/pooling.md). |
| `pgbouncer_max_client_conn` | Client connections the pooler accepts. |
| `pgbouncer_default_pool_size` | Backend connections per user and database pair. |
| `pgbouncer_max_prepared_statements` | Protocol-level prepared statements tracked in transaction mode. |
| `pgbouncer_ignore_startup_parameters` | Startup parameters the pooler accepts and discards. |
| `pgbouncer_client_tls_sslmode` | TLS policy on the pooled endpoint. |
| `pgbouncer_tls_cert_source` | Controller-side certificate the pooler serves. |
| `pgbouncer_tls_key_source` | Controller-side key for that certificate. |
| `pgbouncer_hba_rules` | Client authentication rules for the pooled endpoint only. |
| `pgbouncer_limit_nofile` | File descriptor limit for the service unit. |

See the [Pooling Configuration](../configuration/pooling.md) document for
descriptions and defaults.

## How It Works

The role writes every file the pooler reads before starting the service, so
the first start already has the restart policy, the credentials, the rules and
the certificate in place.

1. Create `/etc/pgbouncer` mode `0750`, owned by the platform's pgBouncer
   service user.
2. Write `/etc/systemd/system/pgbouncer.service.d/override.conf` with
   `Restart=always`, `RestartSec=2`, `StartLimitIntervalSec=0` and
   `LimitNOFILE`.
3. Write `/etc/pgbouncer/userlist.txt` with a single entry for
   `pgbouncer_auth_user`.
4. Copy the TLS certificate and key from the controller to
   `/etc/pgbouncer/`, unless `pgbouncer_client_tls_sslmode` is `disable`.
5. Render `/etc/pgbouncer/pg_hba.conf`, the pooler's own client
   authentication rules.
6. Render `/etc/pgbouncer/pgbouncer.ini`.
7. On Debian-based systems, stop, disable and mask `pgbouncer.socket`.
8. Enable the service, and restart it when any of the files above changed.

### Databases and Backends

The pooler routes every requested database to the node's local PostgreSQL:

```ini
[databases]
* = host=127.0.0.1 port=5432
```

The client's database name and role are forwarded as they arrive, so the
pooled endpoint exposes the same databases as the direct one. PostgreSQL
already admits that loopback connection: `setup_postgres` writes
`host all all 127.0.0.1/32 scram-sha-256` in a simple cluster, and Patroni
renders the same rule in an HA one, so neither PostgreSQL's configuration nor
Patroni's changes for pooling.

### Authentication

The pooler keeps no list of PostgreSQL passwords. It sets `auth_type = hba`,
so its own `pg_hba.conf` decides which method each client is offered, and then
resolves the requested role's stored SCRAM verifier by calling the lookup
`setup_postgres` created:

```ini
auth_user = pgbouncer_auth
auth_query = SELECT username, password FROM pgbouncer.get_auth($1)
auth_dbname = postgres
```

Any PostgreSQL role therefore works through the pooler, including a role
created long after deployment, and a rotated password takes effect
immediately. `userlist.txt` holds one line, for `pgbouncer_auth_user` itself,
because the pooler has to authenticate to PostgreSQL before it can run the
lookup. That password is stored in plain text because a stored SCRAM verifier
cannot be used to log in; pgBouncer derives the verifier from it, so SCRAM is
still what goes on the wire.

`admin_users` and `stats_users` name `pgbouncer_auth_user` and nobody else.
The admin console cannot use `auth_query`, so its users must appear in
`auth_file`, and that is the only account there.

### Client Authentication Rules

The pooler enforces its own rule file rather than PostgreSQL's. It cannot
share PostgreSQL's: on RHEL-based systems `pg_hba.conf` lives in a `0700`
PGDATA owned by `postgres` while the pooler runs as `pgbouncer`. The rendered
file admits the following, in order:

- `pgbouncer_auth_user` over the unix socket, for the admin console.
- `postgres` over the unix socket, mirroring PostgreSQL's own local rule.
- Nothing else as `pgbouncer_auth_user`: the next rules reject it on every
  address, including the replication pseudo-database, which the `all` keyword
  does not cover. Its one privilege is the credential lookup, which returns any
  role's stored verifier, and the loopback and proxy rules below name every
  role — so without an explicit rejection it would be a network login as well.
  Administration is over the socket only.
- The node's own loopback address.
- Every pgEdge node in the cluster, for `pgedge_user` and `db_user`.
- The zone's HAProxy nodes, plus `proxy_node` when it is set, for every role.
- `custom_hba_rules`, which also apply to PostgreSQL.
- `pgbouncer_hba_rules`, which apply to the pooled endpoint alone.

The rules are rendered from the same variables that drive the PostgreSQL
rules, so the two lists stay in step. They differ deliberately in six ways:
physical replication rules are not mirrored, because a replication connection
cannot be pooled; the rules `setup_backrest` adds for the backup host are not
mirrored either; `pgbouncer_hba_rules` has no PostgreSQL counterpart; the
proxy rules admit every role rather than the cluster's two; the local rule
for the authentication user exists because the pooler has an admin console and
PostgreSQL does not; and that user is rejected on every host rule, which
PostgreSQL needs no counterpart to because it has no such account.

The proxy rules are the one place the pooled rules are wider than the direct
ones. HAProxy's pooled listener is TCP passthrough, so the pooler sees the
proxy's address rather than the client's, and a client-address rule cannot
gate that path at all. Restrict it at the proxy or in the network.

### TLS

PostgreSQL presents a certificate on every node, so a pooled client should not
have to drop to cleartext to use the pooler. The role stages the same
certificate `setup_postgres` generated, from the controller-side directory
rather than from PGDATA on the node, and points `client_tls_cert_file` at it.
The controller is the source because on an HA replica the PGDATA copy arrives
with Patroni's clone, which may not have finished when this role runs. The
pooler needs its own copy because on RHEL-based systems it runs as `pgbouncer`
and cannot read a `0700` PGDATA.

The default `pgbouncer_client_tls_sslmode` of `allow` accepts exactly what the
direct endpoint accepts today: TLS when the client asks for it, plaintext when
it does not. `require` makes TLS mandatory on the pooled endpoint. `disable`
turns it off and skips the certificate entirely, which also makes any
`hostssl` or `hostnossl` rule in the pooler's HBA file meaningless.
`verify-ca` and `verify-full` are not supported, because they need the
`pg_hba.conf` option syntax pgBouncer cannot parse.

### Service Unit

Both packaged units ship `LimitNOFILE` commented out, leaving the pooler with
systemd's default of 1024, fewer descriptors than `max_client_conn` alone.
The drop-in budgets two descriptors per client connection plus a fixed
allowance for the idle server pools, the listening sockets, the log and the
admin console.

`Restart=always` with `StartLimitIntervalSec=0` is the mitigation for the
deliberate failure mode: nothing fails a pooled client over to PostgreSQL,
because pooled and direct connections resolve against different `pg_hba`
rules and are not interchangeable. A dead pooler is an outage of the pooled
endpoint by design.

## Usage Examples

In the following example, the playbook configures the pooler with defaults on
every node of a pooled cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pgbouncer_auth_password: "{{ vault_pgbouncer_auth_password }}"
  roles:
    - role: setup_pgbouncer
      when: pgbouncer_enabled | bool
```

In the following example, the playbook puts the pooler in transaction mode
with prepared statement tracking, requires TLS on the pooled endpoint, and
admits one application subnet to that endpoint alone:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    pgbouncer_auth_password: "{{ vault_pgbouncer_auth_password }}"
    pgbouncer_pool_mode: transaction
    pgbouncer_max_prepared_statements: 200
    pgbouncer_client_tls_sslmode: require
    pgbouncer_hba_rules:
      - databases: demo
        users: appuser
        source: 10.0.4.0/24
        method: scram-sha-256
  roles:
    - role: setup_pgbouncer
      when: pgbouncer_enabled | bool
```

## Artifacts

This role generates the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/pgbouncer/pgbouncer.ini` | Modified | Pooler configuration, replacing the packaged default. |
| `/etc/pgbouncer/pg_hba.conf` | New | Client authentication rules for the pooled endpoint. |
| `/etc/pgbouncer/userlist.txt` | New | The pooler's own PostgreSQL login, mode `0640`. |
| `/etc/pgbouncer/server.crt` | New | Certificate presented to pooled clients. Skipped when client TLS is disabled. |
| `/etc/pgbouncer/server.key` | New | Key for that certificate, mode `0600`. Skipped when client TLS is disabled. |
| `/etc/systemd/system/pgbouncer.service.d/override.conf` | New | Restart policy and file descriptor limit. |

## Platform-Specific Behavior

The role uses each platform's own runtime paths and service user. It creates
`/etc/pgbouncer` and `/etc/systemd/system/pgbouncer.service.d` to hold the
files above, and no others: the log and socket directories come from the
package, and log rotation is left to whatever the platform already provides
rather than to a rule of the role's own.

| | RHEL-based | Debian-based |
|---|---|---|
| service user | `pgbouncer` | `postgres` (the package creates no `pgbouncer` user) |
| log file | `/var/log/pgbouncer/pgbouncer.log` | `/var/log/postgresql/pgbouncer.log` |
| pid file | `/run/pgbouncer/pgbouncer.pid` | `/var/run/postgresql/pgbouncer.pid` |
| unix socket directory | `/run/pgbouncer`, mode `0700` | `/var/run/postgresql`, mode `2775` |
| log rotation | `/etc/logrotate.d/pgbouncer`, from the package | the `pgedge-postgresql-common` glob over `/var/log/postgresql/*.log` |

The socket directory permissions decide who can administer the pooler
locally: `root` on RHEL-based systems, `root` or `postgres` on Debian-based
ones. `/var/run/postgresql` is not an option on RHEL, where it is mode `0755`
and owned by `postgres`, so the pooler cannot bind in it.

On Debian-based systems the role also masks `pgbouncer.socket`. The package
ships that unit disabled, for systemd socket activation, and this collection
does not use activation: the pooler is always-on, and `pgbouncer.ini` stays
the authority on the port and listen address. Masking keeps the two
mechanisms from both being live.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. It restarts
pgBouncer only when the drop-in, the userlist, the certificate, the HBA file
or `pgbouncer.ini` changed, and otherwise ensures the service is running. The
restart is a task rather than a handler on purpose: with `any_errors_fatal`, a
notified handler never fires when a later role fails, which would leave the
pooler running stale configuration while Ansible reported the change as
applied.

!!! info "Administering the Pooler"
    Reach the admin console over the unix socket as the authentication user,
    which is the one account `auth_file` holds:

    ```bash
    sudo psql -h /run/pgbouncer -p 6432 -U pgbouncer_auth pgbouncer -c 'SHOW POOLS'
    ```

    Use `-h /var/run/postgresql` on Debian-based systems.
