# Proxy Configuration

These parameters control the proxy layer behavior. They are not explicitly
tied to HAProxy, which serves as the default proxy implementation for this
collection.

## The Port Model

A high availability cluster has four ports, in two pairs. On each pgEdge node,
`pg_port` is PostgreSQL and `pgbouncer_port` is the node's connection pooler,
when the node runs one. On the proxy layer, `proxy_port` fronts `pg_port` and
`pooler_port` fronts `pgbouncer_port`.

| Port | Default | Listens on | Reaches |
|------|---------|-----------|---------|
| `pg_port` | 5432 | each pgEdge node | PostgreSQL |
| `pgbouncer_port` | 6432 | each pooled pgEdge node | that node's pooler |
| `proxy_port` | 5432 | each HAProxy node | the zone's current primary, directly |
| `pooler_port` | 6432 | each HAProxy node | the pooler on the zone's current primary |

The proxy-layer ports are separate settings from the node ports because
HAProxy may share a host with PostgreSQL and pgBouncer, where identical values
collide. The `init_server` role rejects a collision before deployment.

## proxy_port

- Type: Integer
- Default: `5432`
- Description: This parameter specifies the port that Spock uses for
  subscription connections to remote zones. Setting this to a value different
  from `pg_port` allows HAProxy to run on the same host as Postgres, with
  HAProxy listening on one port and Postgres on another.

In the following example, the inventory moves Postgres to port 5433 and
leaves the standard port for HAProxy:

```yaml
pgedge:
  vars:
    pg_port: 5433
    proxy_port: 5432
```

## proxy_node

- Type: String
- Default: (none)
- Scope: Host variable
- Description: This parameter explicitly specifies the proxy endpoint to use
  for Spock subscriptions in HA clusters. When this parameter is unset, the
  collection uses the first HAProxy node in the same zone as the remote pgEdge
  node, or falls back to the first pgEdge node in that zone if no HAProxy node
  is present.

In the following example, the inventory specifies a custom proxy endpoint for
a node:

```yaml
hosts:
  node1.example.com:
    zone: 1
    proxy_node: custom-proxy.example.com
```

!!! note "Proxy Override"
    This parameter can reference an external proxy or load balancer not
    managed by this collection. External proxies must support HTTP health
    checks against the Patroni REST API on port 8008 for correct routing.

## pooler_port

- Type: Integer
- Default: `6432`
- Description: This parameter specifies the proxy-layer port for the pooled
  listener, mirroring the way `proxy_port` fronts `pg_port`. Nothing is
  emitted on this port unless `pgbouncer_enabled` is set, so the parameter is
  inert in a cluster that does not pool.

In the following example, the inventory runs HAProxy on a pgEdge node and
gives all four ports distinct values:

```yaml
pgedge:
  vars:
    pg_port: 5433
    pgbouncer_port: 6433
    proxy_port: 5432
    pooler_port: 6432
```

## haproxy_extra_routes

- Type: Dictionary
- Default: `{replica: {port: 5433}}`
- Description: This parameter provides additional HAProxy listeners
  corresponding to
  [Patroni REST endpoint](https://patroni.readthedocs.io/en/latest/rest_api.html)
  check types. Each entry requires a `port` sub-key and accepts an optional
  `lag` sub-key for maximum replication lag. The collection uses the route key
  as the Patroni check type.

In the following example, the inventory configures replica routing with a lag
limit and a synchronous replica route:

```yaml
haproxy_extra_routes:
  # Connect only to replicas with less than 1 MB of lag on port 5433
  replica:
    port: 5433
    lag: 1024

  # Connect only to synchronous replicas on port 5434
  sync:
    port: 5434
```

These listeners always route directly to `pg_port`. A pooled route is not
available; the pooled listener on `pooler_port` is the only one that reaches a
pooler.

## haproxy_max_conn

- Type: Integer
- Default: `100`, plus `haproxy_pooler_max_conn` where the cluster pools
- Description: This parameter specifies HAProxy's global connection ceiling,
  which has to cover the sum of the listeners' own. The direct listeners keep
  the budget this collection has always given them, and a pooled cluster adds
  the pooled listener's ceiling on top, so a cluster that does not pool renders
  exactly the configuration it did before pooling existed.

## haproxy_pooler_max_conn

- Type: Integer
- Default: `pgbouncer_max_client_conn` on the zone's first node
- Description: This parameter specifies what the pooled listener accepts. Only
  the leader's pooler takes traffic at any moment, so the ceiling is one
  pooler's `max_client_conn` rather than the sum across pooled nodes.

## The Pooled Listener

When `pgbouncer_enabled` is set, `setup_haproxy` emits an additional listener
in every zone:

```
listen pg-pooler
    bind *:6432 maxconn 1000
    mode tcp
    option httpchk
    http-check expect status 200
    default-server inter 3s fall 3 rise 2 on-marked-down shutdown-sessions

    server 192_168_6_10 192.168.6.10:6432 check port 8008
    server 192_168_6_11 192.168.6.11:6432 check port 8008
    server 192_168_6_12 192.168.6.12:6432 check port 8008
```

Three properties of that listener are deliberate.

**Its backends are every pgEdge node in the proxy's own zone**, the same
servers the direct listener carries, differing only in the port. That follows
from pooling being cluster-wide, and it is what keeps the endpoint available:
because the check is the leader endpoint, only the pooler on the current leader
is ever up, and any node of the zone can become the leader.

**Its health check is Patroni's REST API on port 8008**, exactly as the direct
listeners use it. A TCP check against `pgbouncer_port` would mark every pooled
node up and send writes to replicas.

**It never falls back to PostgreSQL.** Because the check reads Patroni rather
than the pooler, a dead pooler on the leader is an outage of the pooled
endpoint rather than a silent reroute to the direct one. That is the intended
behavior, since pooled and direct connections resolve against different
`pg_hba` rules and are not interchangeable. The pooler's
`Restart=always` unit is the mitigation. With the pooler stopped on the
leader, the pooled listener answers `server closed the connection
unexpectedly` while the direct listener keeps serving.

The existing listeners are unchanged by pooling. In particular, **Spock only
ever uses the direct listener**: cross-zone subscriptions connect to
`proxy_port`, so replication never passes through a pooler and is unaffected
by `pgbouncer_pool_mode` or by a pooler failure.

## The Connection Budget

Pooling adds a link to a chain the operator sizes as a whole:

```
HAProxy haproxy_pooler_max_conn
  -> pgBouncer pgbouncer_max_client_conn
    -> pgBouncer pgbouncer_default_pool_size (per user and database pair)
      -> PostgreSQL max_connections
```

`haproxy_pooler_max_conn` defaults to the pooled node's own
`pgbouncer_max_client_conn`, and `haproxy_max_conn` covers the sum of every
listener, so the first two links stay in step without configuration. The last
link does not: this collection does not set PostgreSQL's `max_connections`, so
a raised `pgbouncer_default_pool_size` has to be checked against it.

In session mode the pool size is a hard concurrency limit rather than a
multiplier. See [Pooling Configuration](pooling.md#pgbouncer_pool_mode).

!!! note "Reading the Defaults From the Pooled Node"
    HAProxy runs on hosts that are not pgEdge nodes, and role defaults never
    appear in `hostvars`. `haproxy_pooler_max_conn` therefore reads
    `pgbouncer_max_client_conn` from the zone's first node where the inventory
    sets one (group variables on `pgedge` is the usual place, beside
    `pgbouncer_enabled` itself), and otherwise falls back to the default the
    HAProxy host itself carries. Set the value on the `pgedge` group, not on
    individual hosts, so every node in a zone agrees.
