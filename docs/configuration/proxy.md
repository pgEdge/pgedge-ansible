# Proxy Configuration

These parameters control the proxy layer behavior. They are not explicitly
tied to HAProxy, which serves as the default proxy implementation for this
collection.

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
