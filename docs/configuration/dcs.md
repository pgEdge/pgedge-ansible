# DCS Configuration

Patroni stores cluster state in a distributed configuration store (DCS) and
uses that store to elect a primary node. The `setup_patroni` role writes the
DCS connection details into the Patroni configuration file. By default the
collection deploys an etcd cluster and points Patroni at that cluster, but the
inventory can direct Patroni at any store Patroni supports, including a store
this collection does not manage.

## patroni_dcs

- Type: Dictionary
- Default: `type: etcd3` with no `parameters` key
- Description: This parameter selects the distributed configuration store
  that Patroni uses and supplies the connection settings for the store. The
  dictionary accepts a `type` key and a `parameters` key. The `parameters` key
  is optional only when `type` is `etcd` or `etcd3`.

The `type` key names the store, and the collection writes the value directly
as the DCS section name in the Patroni configuration file. The `init_server`
role validates the value on HA clusters and stops the play when the value is
not recognized. The following table describes the accepted values:

| Value | Description |
|-------|-------------|
| etcd3 | etcd accessed through the version 3 API. This value is the default and the only store the collection installs and configures. |
| etcd | etcd accessed through the legacy version 2 API. |
| consul | A Consul cluster provided and managed outside the collection. |
| zookeeper | An Apache ZooKeeper ensemble provided and managed outside the collection. |
| exhibitor | A ZooKeeper ensemble fronted by Netflix Exhibitor. |

Patroni also supports a `kubernetes` type, which this collection rejects.
Patroni does not accept an endpoint for that type. It discovers the API server
from the environment variables and service account files that Kubernetes
injects into a pod, and falls back to a kubeconfig file when those are absent.
This collection installs Patroni as a systemd service on ordinary hosts, where
neither source is present, so the type cannot reach an API server.

The `parameters` key holds the settings Patroni needs to reach the store. The
collection passes these settings through to the configuration file without
inspecting or validating the contents, so consult the
[Patroni YAML Configuration reference](https://patroni.readthedocs.io/en/latest/yaml_configuration.html)
for the settings each store accepts.

When `type` is `etcd` or `etcd3` and the inventory omits `parameters`, the
collection substitutes defaults that match the etcd cluster built by the
`install_etcd` and `setup_etcd` roles. The following table describes those
defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| host | INVENTORY_HOSTNAME:2379 | Client endpoint on the local node, taken from the inventory hostname. |
| ttl | 30 | Seconds before the leader key expires. |
| protocol | https | Transport used for client connections. |
| cacert | PATRONI_TLS_DIR/ca.crt | Certificate authority that signed the etcd server certificates. |
| cert | PATRONI_TLS_DIR/patroni.crt | Client certificate Patroni presents to etcd. |
| key | PATRONI_TLS_DIR/patroni.key | Private key for the client certificate. |

The `patroni_tls_dir` parameter sets the directory in the last three defaults.
For more information, see the
[etcd Configuration](etcd.md) document.

Supplying `parameters` replaces every default rather than merging with the
defaults, so an inventory that sets `parameters` must list all settings the
store requires. Ansible replaces the whole `patroni_dcs` dictionary when the
inventory overrides the parameter, so an inventory that sets `parameters` must
also set `type`.

Every other `type` requires `parameters`, because the collection has no way to
guess the address or credentials of a store it does not deploy. The
`init_server` role asserts this on HA clusters and stops the play with the
following message when the key is missing or empty:

```text
patroni_dcs.parameters is required when patroni_dcs.type is 'consul'
```

The check runs before any bootstrapping, so a missing key fails immediately
rather than part way through configuring Patroni.

In the following example, the inventory keeps the default store and connects
Patroni to the etcd cluster the collection builds:

```yaml
is_ha_cluster: true
```

In the following example, the inventory points Patroni at an existing etcd
cluster running on dedicated hosts:

```yaml
is_ha_cluster: true

patroni_dcs:
  type: etcd3
  parameters:
    hosts:
      - etcd1.example.com:2379
      - etcd2.example.com:2379
      - etcd3.example.com:2379
    ttl: 30
    protocol: https
    cacert: /etc/patroni/tls/ca.crt
```

In the following example, the inventory replaces etcd with a Consul cluster:

```yaml
is_ha_cluster: true

patroni_dcs:
  type: consul
  parameters:
    host: consul.example.com:8500
    token: 00000000-0000-0000-0000-000000000000
    register_service: true
```

## Client Libraries

Patroni needs a Python client library for the store it talks to, and the
library differs by store. The `install_patroni` role installs the library that
matches `patroni_dcs.type`, drawing it from the pgEdge repository on RHEL
systems and from the distribution repository on Debian systems. The following
table describes the library each store requires:

| Store type | Client library |
|------------|----------------|
| etcd3, etcd | The etcd client, installed by default. |
| consul | The Consul client. |
| zookeeper, exhibitor | The Kazoo ZooKeeper client. |

Patroni fails at startup with a missing module error when the library for the
configured store is absent, so confirm the repositories the nodes use provide
the library before selecting a store other than etcd.

## Using an External Store

The collection installs and configures etcd only, so a deployment that uses
another store must provide and maintain that store separately. Omit the
`install_etcd` and `setup_etcd` roles from the playbook when the store already
exists outside the cluster.

The `setup_patroni` role generates a Patroni client certificate signed by the
etcd certificate authority, and the role skips that step when `type` is
neither `etcd` nor `etcd3`. An external store must therefore carry its own
credentials in `parameters`, and any certificate files those credentials
reference must already exist on each pgEdge node. This is why `parameters` is
mandatory for an unmanaged store: it is the only place the store's address and
credentials can come from.

### Sharing One Store Across Zones

Patroni stores its cluster state under a key built from the namespace and the
scope, and the collection derives both from values that are identical on every
node. The collection deploys its own etcd cluster once per zone, so each zone
writes to a separate store and the shared key never causes a conflict. An
external store removes that separation whenever a single deployment serves
more than one zone, and both zones then claim the same key.

The symptom is that one zone deploys normally and the other fails, because the
zone that reaches the store second reads a Postgres system identifier
belonging to the first zone. Patroni refuses to join a cluster it does not
recognize and stops with the following message:

```text
CRITICAL: system ID mismatch, node pgedge4 belongs to a different cluster
```

Which zone fails varies between deployments, because the outcome depends on
which zone reaches the store first. Set `patroni_namespace` per zone to give
each zone its own key prefix:

```yaml
patroni_namespace: "/db/zone{{ zone }}/"
```

The default is `/db/` for every zone, which preserves the behavior of earlier
releases. A store that serves only one zone needs no change, and neither does
a deployment that gives each zone its own store.

### Example

In the following example, the play that bootstraps the pgEdge nodes omits
`install_etcd` and `setup_etcd` so that Patroni uses an external Consul
cluster:

```yaml
- hosts: pgedge
  any_errors_fatal: true

  collections:
    - pgedge.platform

  vars:
    is_ha_cluster: true
    patroni_dcs:
      type: consul
      parameters:
        host: consul.example.com:8500

  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
    - install_patroni
    - install_backrest
    - setup_patroni
    - setup_backrest
```

The remaining plays in the playbook are unchanged. For the full playbook
structure, see the
[Tutorial - Deploying an Ultra-HA Cluster](../ultra_ha.md) document.

The Ultra-HA end-to-end test covers an external Consul cluster alongside the
default etcd configuration. To run that variant locally, pass the store name
as the third argument to the test script:

```bash
./tests/run-test.sh ultra-ha rocky9 consul
```
