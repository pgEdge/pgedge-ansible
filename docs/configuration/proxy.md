# Proxy Configuration

Some cluster parameters control proxy layer behavior. These parameters are not
explicitly linked to HAProxy, which serves as a convenient default for this
collection.

## proxy_port

- Type: Integer
- Default: `5432`
- Description: This parameter specifies the port for HAProxy to listen on. You
  can set this parameter to differ from the `pg_port` parameter to run HAProxy
  on the same host as Postgres.

```yaml
proxy_port: 5432
```

## proxy_node

- Type: String
- Default: None
- Scope: Host variable
- Description: This parameter explicitly specifies the proxy endpoint to use
  for Spock subscriptions in HA clusters. The collection uses the first HAProxy
  node in the same zone when you do not set this parameter.

```yaml
hosts:
  node1.example.com:
    zone: 1
    proxy_node: custom-proxy.example.com
```

!!! note "Proxy Override"
    This parameter primarily overrides or acts in place of nodes in the
    `haproxy` inventory group. You can use this setting to specify external
    proxies or load balancers. Such proxies will need HTTP check capabilities
    to interact with the Patroni REST service for proper node routing.

## haproxy_extra_routes

- Type: Dictionary
- Default:

    ```yaml
    haproxy_extra_routes:
      replica:
        port: 5433
    ```

- Description: This parameter provides additional HAProxy routes for the
  [Patroni REST interface](https://patroni.readthedocs.io/en/latest/rest_api.html).
  Each route requires a `port` value; you can optionally specify a `lag` value
  for maximum replication lag. The collection uses the route key as the check
  type.

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
