# Proxy Configuration

Some cluster parameters are specific to the proxy layer. This is not explicitly linked to HAProxy, which is only a convenient default provided by this collection.

## proxy_port

- **Type:** Integer
- **Default:** `5432`
- **Description:** Port for HAProxy to listen on. Can differ from `pg_port` to run HAProxy on the same host as PostgreSQL.

```yaml
proxy_port: 5432
```

## proxy_node

- **Type:** String
- **Default:** None
- **Scope:** Host variable
- **Description:** Explicitly specify the proxy endpoint to use for Spock subscriptions in HA clusters. If not set, uses the first HAProxy node in the same zone.

```yaml
hosts:
  node1.example.com:
    zone: 1
    proxy_node: custom-proxy.example.com
```

!!! note "Proxy Override"
    This parameter is primarily to _override_ or act in place of nodes in the `haproxy` inventory group. This setting is provided to use external proxies or load balancers. Be aware that such proxies will need to have HTTP check capabilities to interact with the Patroni REST service for proper node routing.

## haproxy_extra_routes

- **Type:** Dictionary
- **Default:**
    ```yaml
    haproxy_extra_routes:
      replica:
        port: 5433
    ```
- **Description:** Additional HAProxy routes for the [Patroni REST interface](https://patroni.readthedocs.io/en/latest/rest_api.html). Each route requires a `port`; optionally specify `lag` for maximum replication lag. The key for the route will be used for the type of check being performed.

```yaml
haproxy_extra_routes:
  # Connect only to replicas with less than 1MB of lag through port 5433
  replica:
    port: 5433
    lag: 1024

  # Connect only to synchronous replicas through port 5434
  sync:
    port: 5434
```
