# Pooling Configuration

The pgEdge Ansible Collection can run pgBouncer on pgEdge nodes to provide a
pooled connection endpoint beside the direct PostgreSQL one. The
`install_pgbouncer` and `setup_pgbouncer` roles use the parameters on this
page.

Pooling is opt-in by inventory group. A node runs a pooler when it belongs to
the `pgbouncer` group, which must be a subset of the `pgedge` group; nodes
outside that group are untouched. See
[Inventory Structure](inventory.md#pgbouncer-optional) for the group, and
[Proxy Configuration](proxy.md#pooler_port) for the HAProxy listener that
fronts the poolers in a high availability cluster.

## How Pooling Fits the Cluster

Each pooler forwards every database to the PostgreSQL instance on its own
node, over `127.0.0.1`. A pooled node therefore serves two endpoints:
`pg_port` for direct connections and `pgbouncer_port` for pooled ones.

The two endpoints are not interchangeable. They resolve against different
client authentication rules, so a client that reaches one is not guaranteed to
reach the other, and nothing in the collection fails a pooled client over to
PostgreSQL. A dead pooler is an outage of the pooled endpoint by design;
`Restart=always` in the pooler's service unit is the mitigation.

Spock replication never routes through a pooler. Cross-zone subscriptions use
`proxy_port` on the direct listener, so pooling changes nothing about
replication.

In a high availability cluster, pool every node of a zone or none of them. The
pooled HAProxy listener health-checks Patroni's leader endpoint, so it routes
only to the pooler on the current leader, and a failover to an unpooled node
leaves the pooled endpoint with no reachable backend.

## pgbouncer_port

- Type: Integer
- Default: `6432`
- Description: This parameter specifies the port each pooler listens on. It
  must differ from `pg_port`, because a pooled node runs both services and the
  pooler's unix socket is named after its port, so an equal value collides
  with PostgreSQL's own socket as well as its TCP port. The `init_server` role
  rejects the collision before anything is provisioned.

In the following example, the inventory moves the pooled endpoint off the
default port:

```yaml
pgedge:
  vars:
    pgbouncer_port: 6433
```

## pgbouncer_listen_addr

- Type: String
- Default: `*`
- Description: This parameter specifies the addresses the pooler binds. The
  default accepts connections on every interface, which is what a pooled
  endpoint fronted by HAProxy needs. Set it to a specific address to narrow
  the exposure.

## pgbouncer_auth_user

- Type: String
- Default: `pgbouncer_auth`
- Description: This parameter specifies the PostgreSQL role the pooler logs in
  as. The `setup_postgres` role creates the role wherever a zone has a pooled
  node, with `LOGIN` and `NOINHERIT` and no other privilege than executing the
  credential lookup. It is also the account that reaches the pooler's admin
  console.

## pgbouncer_auth_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for
  `pgbouncer_auth_user`. It is the only password the collection writes to disk
  in plain text, in the pooler's `auth_file`, and `init_server` refuses to
  deploy a pooled cluster while it is still `secret`. Store it in a vault.

In the following example, the inventory takes the password from a vault:

```yaml
pgedge:
  vars:
    pgbouncer_auth_password: "{{ vault_pgbouncer_auth_password }}"
```

## pgbouncer_pool_mode

- Type: String
- Default: `session`
- Options: `session`, `transaction`
- Description: This parameter specifies how much of a session the pooler is
  allowed to reuse. It is the one pooling setting with consequences beyond
  performance.

`session` hands a client one backend for the whole connection and returns it
only at disconnect. Nothing about the session is shared, so every client sees
exactly the PostgreSQL it would see unpooled. The pool is then a hard
concurrency limit rather than a multiplier: when `pgbouncer_default_pool_size`
is below the number of concurrent clients, the clients without a backend
simply wait.

`transaction` returns the backend at the end of every transaction, which is
what multiplexes many clients onto few backends. The cost is that anything
living outside a transaction is no longer reliably the client's own. pgBouncer
runs `server_reset_query` only in session mode, so in transaction mode a `SET`
stays on the backend and the next client to use it inherits the value. The
same applies to advisory locks, `LISTEN`/`NOTIFY`, temporary tables, `WITH
HOLD` cursors, and session-level prepared statements. Applications that touch
none of those pool safely; applications that do need session mode, or must set
their state inside each transaction.

## pgbouncer_default_pool_size

- Type: Integer
- Default: `25`
- Description: This parameter specifies how many backend connections the
  pooler opens per user and database pair. In session mode this is also the
  number of clients that can be served at once.

## pgbouncer_max_client_conn

- Type: Integer
- Default: `1000`
- Description: This parameter specifies how many client connections the pooler
  accepts. It also sizes two things outside `pgbouncer.ini`: the file
  descriptor limit in the pooler's service unit, and the pooled HAProxy
  listener's `maxconn`. See
  [the connection budget](proxy.md#the-connection-budget).

## pgbouncer_max_prepared_statements

- Type: Integer
- Default: `0`
- Description: This parameter specifies how many protocol-level prepared
  statements the pooler tracks per connection. Above `0`, pgBouncer keeps
  track of them itself and replays each one onto whichever backend a
  transaction lands on, which is what makes prepared statements usable in
  transaction mode.

Without it, a driver that keeps server-side prepared statements across
transactions eventually names one the new backend has never seen. pgJDBC and
psycopg3 both start doing this once a statement passes their prepare
threshold, so the failure arrives after some traffic rather than on the first
query. Turning the driver's threshold off, or putting it in simple-query mode,
is the client-side alternative.

The collection writes this value unconditionally, including `0`, because
pgBouncer 1.24 and later default to `200` when the parameter is omitted.

## pgbouncer_ignore_startup_parameters

- Type: String
- Default: `extra_float_digits`
- Description: This parameter lists the startup parameters the pooler accepts
  from a client and then discards. pgBouncer refuses a connection outright,
  with `FATAL: unsupported startup parameter`, when a client asks for a
  parameter it does not track, and it inspects the contents of `options` the
  same way.
  Naming a parameter here stops the refusal, and that is all it does: the
  value is not carried to the backend.

`extra_float_digits` is in the default because pgJDBC sends it on every
connection and discarding it costs nothing: it affects the text precision of
floats, not results.

!!! warning "Think Twice Before Adding search_path"
    Naming `search_path` here does not forward it. The client connects and
    then resolves every unqualified name against the default search path, with
    no error on either side. A hard failure at connect time is the better
    outcome, so put schema selection in the role's `search_path` or in an
    explicit `SET`.

## pgbouncer_client_tls_sslmode

- Type: String
- Default: `allow`
- Options: `disable`, `allow`, `prefer`, `require`
- Description: This parameter specifies the TLS policy on the pooled endpoint.
  The collection stages the certificate `setup_postgres` generated, so the
  pooled and direct endpoints present the same certificate and replacing one
  replaces both.

The default `allow` accepts exactly what the direct endpoint accepts: TLS when
the client asks for it, plaintext when it does not, so enabling pooling
changes no existing client's behavior. `require` makes TLS mandatory on the
pooled endpoint. `disable` turns it off and omits the certificate entirely,
which also makes any `hostssl` or `hostnossl` rule in the pooler's rules
meaningless.

`verify-ca` and `verify-full` are not accepted. Both demand a client
certificate, which needs the `pg_hba.conf` option syntax pgBouncer cannot
parse. The `init_server` role rejects an unsupported value before deployment.

## pgbouncer_tls_cert_source

- Type: String
- Default: `tls/postgres/server.crt`
- Description: This parameter specifies the controller-side certificate the
  pooler serves to clients, relative to the playbook's own directory. The
  default is the staging directory `setup_postgres` generates into, which is
  also where PGDATA's copy came from. Point it at a different certificate to
  change what the pooled endpoint presents.

## pgbouncer_tls_key_source

- Type: String
- Default: `tls/postgres/server.key`
- Description: This parameter specifies the controller-side private key that
  matches `pgbouncer_tls_cert_source`. It is installed mode `0600`.

## pgbouncer_hba_rules

- Type: List of dictionaries
- Default: `[]`
- Description: This parameter provides additional client authentication rules
  for the pooled endpoint only, in the same shape as `custom_hba_rules`. Each
  rule accepts `contype`, `databases`, `users`, `source`, and `method` keys.
  See [Client Authentication](#client-authentication) below for what the
  pooler admits without them.

In the following example, the inventory admits an application subnet to the
pooled endpoint and to nothing else:

```yaml
pgedge:
  vars:
    pgbouncer_hba_rules:
      - contype: host
        databases: demo
        users: appuser
        source: 10.0.4.0/24
        method: scram-sha-256
```

## pgbouncer_limit_nofile

- Type: Integer
- Default: `pgbouncer_max_client_conn * 2 + 1024`
- Description: This parameter specifies the file descriptor limit in the
  pooler's systemd drop-in. Both packaged units ship `LimitNOFILE` commented
  out, leaving the pooler with systemd's default of 1024, fewer descriptors
  than `max_client_conn` alone. The default budgets two descriptors per client
  connection, for its socket and the backend it is paired with, plus a fixed
  allowance for the idle server pools, the listening sockets, the log, and the
  admin console.

## pgbouncer_package

- Type: String
- Default: `pgedge-pgbouncer`
- Description: This parameter specifies the package `install_pgbouncer`
  installs. The collection requires pgBouncer 1.21 or later, which is where
  `max_prepared_statements` arrived.

## Authentication

The pooler keeps no list of PostgreSQL passwords. It logs in to PostgreSQL as
`pgbouncer_auth_user` and calls a `SECURITY DEFINER` lookup to fetch the
requested role's stored SCRAM verifier:

```ini
auth_user = pgbouncer_auth
auth_query = SELECT username, password FROM pgbouncer.get_auth($1)
auth_dbname = postgres
```

The `setup_postgres` role creates the role and the lookup in the maintenance
database wherever a zone has a pooled node. The function reads `pg_shadow` as
its superuser owner, has a pinned `search_path`, lives in its own schema, and
grants `EXECUTE` to the authentication user alone.

Three consequences follow, and they are the reason the collection maintains no
userlist:

- Every PostgreSQL role works through the pooled endpoint, including a role
  created long after deployment.
- A rotated password takes effect on the pooled endpoint immediately, and the
  old one is refused.
- Only one password is written to disk: `pgbouncer_auth_password`, in
  `/etc/pgbouncer/userlist.txt`. The pooler needs it before it can run the
  lookup, and it is stored in plain text because a stored SCRAM verifier
  cannot be used to log in. pgBouncer derives the verifier from it, so SCRAM
  is still what goes on the wire.

The pooler's admin console is the one path the lookup cannot serve, so
`admin_users` and `stats_users` name `pgbouncer_auth_user` and nobody else.
Reach it over the unix socket:

```bash
sudo psql -h /run/pgbouncer -p 6432 -U pgbouncer_auth pgbouncer -c 'SHOW POOLS'
```

Use `-h /var/run/postgresql` on Debian-based systems. Who can use that path is
bounded by the socket directory rather than by a rule: the directory is mode
`0700` on RHEL-based systems, so `root`, and mode `2775` on Debian-based ones,
so `root` or `postgres`.

## Client Authentication

The pooler enforces its own `pg_hba.conf`, in `/etc/pgbouncer`, rendered from
the same variables that drive the PostgreSQL rules. It cannot share
PostgreSQL's file: on RHEL-based systems that file lives in a `0700` PGDATA
owned by `postgres` while the pooler runs as `pgbouncer`.

`auth_type = hba`, so the rules select the method per client and address and
the lookup supplies the credential to check it against. An address the rules
do not name is refused before any password is considered, with `no
authentication method is found`.

Without any configuration, the pooler admits the following:

| Rule | Purpose |
|------|---------|
| `local all <auth_user> scram-sha-256` | The admin console, over the unix socket. |
| `local all postgres peer` | Local `psql` to the pooled databases. Reachable only where `postgres` can traverse the socket directory, which on RHEL-based systems is nowhere. |
| `host all all 127.0.0.1/32 scram-sha-256` | The node's own loopback. |
| `host <databases> <pgedge_user>,<db_user> <node>/32` | Every pgEdge node in the cluster. |
| `host <databases> all <proxy>/32` | The zone's HAProxy nodes, plus `proxy_node` when it is set. |

An application reaching the pooler across the network is named by none of
those, so it has to be added. Two parameters do that, and the difference
matters:

- `custom_hba_rules` is shared with PostgreSQL. A client named there reaches
  both endpoints.
- `pgbouncer_hba_rules` is pooler-only. A client named there reaches the
  pooled endpoint and cannot connect to PostgreSQL directly, which is usually
  the grant that was meant.

### Rules the Pooler Cannot Enforce

Three limits are worth knowing before writing rules.

**The proxy rules cannot be narrowed by client address.** HAProxy's pooled
listener is TCP passthrough, so the pooler sees the proxy's address and not
the client's. Those rules also name every role rather than the cluster's two,
because the pooled endpoint exists for applications and an application uses
whichever role the operator created for it. This is the one place the pooled
rules are wider than the direct ones, and the rules are first-match, so
nothing added afterwards narrows them. Restrict that path at the proxy or in
the network.

**pgBouncer parses a subset of `pg_hba.conf`.** It rejects the `ident` method
and option syntax such as `clientcert=verify-ca`, and it skips a line it
cannot parse with a warning rather than refusing to start, so a dropped
`reject` rule would leave the pooler quietly more permissive than PostgreSQL.
The `init_server` role validates `custom_hba_rules` and `pgbouncer_hba_rules`
against what the pooler accepts before anything is provisioned: `contype` must
be `local`, `host`, `hostssl`, or `hostnossl`, and `method` must be `trust`,
`reject`, `md5`, `password`, `scram-sha-256`, `peer`, or `cert`.

**`trust` does not mean what it appears to.** A `trust` rule still requires the
role to be listed in `auth_file`, or pgBouncer answers `"trust" authentication
failed`. It also breaks credential pass-through for that client: with no
password collected, the backend login fails with `server login failed: wrong
password type`. Use `password` or `scram-sha-256`.

### Rules That Are Not Mirrored

Two classes of PostgreSQL rule are deliberately absent from the pooler's file.
Physical replication rules are not mirrored, because a replication connection
cannot be pooled and a rule permitting one would only mislead. Neither are the
rules `setup_backrest` adds for the backup host, for the same reason.

!!! warning "Client Libraries Requesting Wire Protocol 3.2"
    A client whose libpq requests PostgreSQL wire protocol 3.2 or later
    cannot connect through a pooler running pgBouncer 1.25.2 or earlier while
    `auth_query` is in use: pgBouncer answers `NegotiateProtocolVersion`
    twice, and the client reports `received duplicate protocol negotiation
    message`. This is an upstream pgBouncer bug with a merged but unreleased
    fix. Every stable libpq defaults to protocol 3.0 and is unaffected. The
    client-side workaround is `max_protocol_version=3.0` in the connection
    string, or `PGMAXPROTOCOLVERSION=3.0` in the environment. See
    [pgBouncer Issues](../troubleshooting/pgbouncer.md#client-reports-a-duplicate-protocol-negotiation-message).
