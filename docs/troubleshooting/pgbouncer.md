# pgBouncer Issues

This page covers the pooled connection endpoint. Pooling is opt-in: only
nodes in the `pgbouncer` inventory group run a pooler. See
[Pooling Configuration](../configuration/pooling.md) for the parameters
referenced here.

The pooler's log is the first place to look. It is at
`/var/log/pgbouncer/pgbouncer.log` on RHEL-based systems and
`/var/log/postgresql/pgbouncer.log` on Debian-based systems:

```bash
sudo tail -n 50 /var/log/pgbouncer/pgbouncer.log
sudo journalctl -u pgbouncer -n 50 --no-pager
```

## Service Fails to Start

**Symptom:** pgBouncer will not start after configuration.

**Solution:** Check the log for the parameter it refused, then confirm nothing
else holds the port:

```bash
sudo journalctl -u pgbouncer -n 50 --no-pager
sudo ss -tlnp | grep -E '5432|6432'
```

Two causes account for most failures. A `pgbouncer_port` equal to `pg_port`
collides with PostgreSQL on both the TCP port and the unix socket, whose name
is derived from the port. The message `unix socket is in use` comes from
whichever process started second. And `client_tls_sslmode` values of
`verify-ca` or `verify-full` are not supported by this collection. The
`init_server` role rejects both before deployment, so a failure here usually
means the pooler was reconfigured by hand.

## Client Cannot Connect: No Authentication Method Is Found

**Symptom:** A client with valid credentials is refused, and reports:

```
psql: error: connection to server ... failed: no authentication method is found
```

**Solution:** This is the pooler's own `pg_hba.conf` refusing the address
before any password is considered. It is a separate file from PostgreSQL's, so
a client that connects to `pg_port` is not necessarily admitted on
`pgbouncer_port`. Inspect what the pooler was given:

```bash
sudo cat /etc/pgbouncer/pg_hba.conf
```

Without configuration, the pooler admits only the cluster's own nodes, the
zone's HAProxy nodes, the node's loopback, and local administration. Name the
client in `pgbouncer_hba_rules` to admit it to the pooled endpoint alone, or in
`custom_hba_rules` to admit it to both endpoints, then re-run the playbook.

In a high availability cluster the pooler sees the proxy's address rather than
the client's, because the pooled HAProxy listener is TCP passthrough. A rule
naming the client's own address cannot admit a connection arriving that way.

## The Pooler Skipped a Rule

**Symptom:** A rule in `custom_hba_rules` or `pgbouncer_hba_rules` has no
effect on the pooled endpoint, and the log carries a warning.

**Solution:** pgBouncer parses a subset of `pg_hba.conf` and skips a line it
cannot parse with a warning rather than refusing to start. Count them:

```bash
sudo grep 'could not parse hba' /var/log/pgbouncer/pgbouncer.log
```

The `ident` method and option syntax such as `clientcert=verify-ca` are the
common causes. This fails open, so a skipped `reject` rule leaves the pooler
more permissive than PostgreSQL. Rewrite the rule using a `contype` of
`local`, `host`, `hostssl`, or `hostnossl` and a `method` of `trust`,
`reject`, `md5`, `password`, `scram-sha-256`, `peer`, or `cert`.

## Client Cannot Connect: Password Authentication Failed

**Symptom:** A client whose password works on `pg_port` is refused on
`pgbouncer_port`.

**Solution:** The pooler holds no password list. It logs in as
`pgbouncer_auth_user` and calls a lookup to fetch the client's stored
verifier, so this symptom usually means the pooler's own login is broken
rather than the client's. Check that the pooler can authenticate and that the
lookup is in place:

```bash
sudo psql -h /run/pgbouncer -p 6432 -U pgbouncer_auth pgbouncer -c 'SHOW VERSION'
sudo -i -u postgres psql -c '\df pgbouncer.get_auth'
```

Use `-h /var/run/postgresql` on Debian-based systems. If the console refuses
the password, `/etc/pgbouncer/userlist.txt` disagrees with the role's password
in PostgreSQL. Re-run `setup_postgres` and `setup_pgbouncer` with the same
`pgbouncer_auth_password`. If the function is missing, `setup_postgres` did not
run with a pooled node in the zone.

A `trust` rule produces the same symptom from the other direction: it collects
no password from the client, so the backend login then fails with `server login
failed: wrong password type`. Use `password` or `scram-sha-256` instead.

## Client Reports a Duplicate Protocol Negotiation Message

**Symptom:** A client fails to connect through the pooler with:

```
received duplicate protocol negotiation message
```

**Solution:** This is an upstream pgBouncer bug, not a configuration problem.
A client whose libpq requests PostgreSQL wire protocol 3.2 or later cannot
connect through pgBouncer 1.25.2 or earlier while `auth_query` is in use,
because pgBouncer answers `NegotiateProtocolVersion` twice. The fix is merged
upstream but not in any released version.

Every stable libpq defaults to protocol 3.0 and is unaffected, so the symptom
appears only with a beta or development client library. Pin the protocol on the
client side:

```bash
psql "host=proxy1.example.com port=6432 dbname=demo max_protocol_version=3.0"
PGMAXPROTOCOLVERSION=3.0 psql -h proxy1.example.com -p 6432 demo
```

Direct connections to `pg_port` are unaffected, so a client that must use a
newer protocol can use the direct endpoint until a fixed pgBouncer ships.

## Admin Console Refused After Authenticating

**Symptom:** A connection to the `pgbouncer` database authenticates and is
then refused with `bouncer config error`.

**Solution:** The admin console is restricted to `admin_users`, which is
`pgbouncer_auth_user` and nobody else. The console cannot use the credential
lookup, so its users must appear in `auth_file`, and that is the only account
there. Connecting as `postgres` passes the HBA rule and is refused at this
point. Use the authentication user:

```bash
sudo psql -h /run/pgbouncer -p 6432 -U pgbouncer_auth pgbouncer -c 'SHOW POOLS'
```

On RHEL-based systems the socket directory is mode `0700` and owned by
`pgbouncer`, so `root` is the only account that can reach it; `postgres` gets
`Permission denied` on the directory, which makes the `local all postgres peer`
rule a no-op there. On Debian-based systems the directory is mode `2775` and
owned by `postgres`, so `root` and `postgres` both reach it.

## Pooled Endpoint Fails While the Direct One Works

**Symptom:** Connections to `pooler_port` on an HAProxy node fail with
`server closed the connection unexpectedly` after a couple of seconds, while
`proxy_port` still serves.

**Solution:** This is the designed behavior when the pooler is down on the
node holding the Patroni leader. The pooled listener health-checks Patroni's
REST API rather than the pooler, so HAProxy accepts the connection, fails to
reach the pooler, and gives up after its retries. Nothing reroutes a pooled
client to PostgreSQL, because the two endpoints resolve against different
`pg_hba` rules and are not interchangeable.

Find the leader and restart its pooler:

```bash
sudo -i -u postgres patronictl -c /etc/patroni/patroni.yml list
sudo systemctl status pgbouncer
sudo systemctl restart pgbouncer
```

The service unit carries `Restart=always`, so this state normally clears
itself. A pooler that keeps dying is a configuration or resource problem, so
check the log.

The same symptom appears with every pooler healthy when the zone pools only
some of its nodes and the leader is one of the others: the pooled listener
routes only to the pooler on the current leader, so it has no reachable
backend. Add the remaining nodes of the zone to the `pgbouncer` group and
re-run the playbook.

## Session State Leaks Between Clients

**Symptom:** A client sees a `search_path`, a temporary table, or another
session setting it never set, or a `LISTEN` never fires.

**Solution:** The pooler is in transaction mode. pgBouncer runs
`server_reset_query` only in session mode, so in transaction mode a `SET`
stays on the backend and the next client to use it inherits the value. The
same applies to advisory locks, `LISTEN`/`NOTIFY`, temporary tables, and
`WITH HOLD` cursors.

Either set the state inside each transaction, or return the pooler to session
mode:

```yaml
pgedge:
  vars:
    pgbouncer_pool_mode: session
```

## Prepared Statement Errors Under Transaction Pooling

**Symptom:** A client works for a while and then fails with a message about an
unknown or unnamed prepared statement.

**Solution:** In transaction mode a driver that keeps server-side prepared
statements across transactions eventually names one the new backend has never
seen. pgJDBC and psycopg3 both start doing this once a statement passes their
prepare threshold, which is why the failure arrives after some traffic rather
than on the first query.

Let the pooler track them instead:

```yaml
pgedge:
  vars:
    pgbouncer_max_prepared_statements: 200
```

The client-side alternatives are turning the driver's prepare threshold off or
putting it in simple-query mode.

## Client Refused With an Unsupported Startup Parameter

**Symptom:** A client cannot connect and reports:

```
FATAL: unsupported startup parameter: search_path
```

**Solution:** pgBouncer refuses a connection that asks for a parameter it does
not track, and it inspects the contents of `options` the same way. Adding the
name to `pgbouncer_ignore_startup_parameters` stops the refusal, but the value
is then discarded rather than forwarded to the backend. For `search_path`,
that trades a loud connect-time failure for every unqualified name resolving
in the wrong schema, silently. Prefer setting the value on the role or in an
explicit `SET` inside the session.

## Clients Wait Instead of Connecting

**Symptom:** Connections to the pooled endpoint hang under load rather than
being refused.

**Solution:** In session mode a client holds its backend for the whole
connection, so `pgbouncer_default_pool_size` is a hard concurrency limit and
further clients wait. Look at the pools:

```bash
sudo psql -h /run/pgbouncer -p 6432 -U pgbouncer_auth pgbouncer -c 'SHOW POOLS'
```

A non-zero `cl_waiting` with `sv_idle` at zero is pool exhaustion. Raise
`pgbouncer_default_pool_size`, checking the result against PostgreSQL's
`max_connections`, which this collection does not manage, or move the
application to transaction mode.

!!! info "The Unpooled Node Still Has the Package"
    `pgedge-enterprise-all` depends on `pgedge-pgbouncer`, so the package is
    present on every pgEdge node, and on Debian-based systems the package
    enables and starts the service against its own default configuration.
    Neither package presence nor service state tells you whether a node is
    pooled. The configuration does: a managed pooler's
    `/etc/pgbouncer/pgbouncer.ini` begins with `# Managed by Ansible`.
