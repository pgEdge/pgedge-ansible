# setup_lakekeeper

The `setup_lakekeeper` role configures Lakekeeper's catalog database, starts
the service, and bootstraps the Iceberg warehouse and namespace ColdFront
commits through.

The role performs the following tasks on inventory hosts:

- Check that the S3-compatible object store is reachable from this host,
  since creating the warehouse makes Lakekeeper write to the bucket to
  prove the credentials work.
- Create the Lakekeeper database role and catalog database, and the five
  extensions its migration needs (`uuid-ossp`, `pgcrypto`, `pg_trgm`,
  `btree_gin`, `btree_gist`) as the Postgres superuser, keeping the
  Lakekeeper role itself unprivileged.
- Generate `/etc/lakekeeper/encryption.key` once and write
  `/etc/lakekeeper/lakekeeper.env`.
- Run `lakekeeper migrate` to create the catalog schema. This is idempotent,
  so it runs on every pass rather than being guarded.
- Start and enable the `lakekeeper` service, restarting only when the
  environment file changed.
- Wait for `/health` to report `ok`, rather than for the port alone to
  accept connections.
- Bootstrap the catalog, create the warehouse over the object store, and
  pre-create the Iceberg namespace.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_lakekeeper` installs the Lakekeeper packages and standalone
  Postgres instance.

## When to Use

Execute this role immediately after `install_lakekeeper`, on the same
dedicated `lakekeeper` host.

```yaml
- hosts: lakekeeper
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_lakekeeper
    - setup_lakekeeper
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `lakekeeper_host` | Address Lakekeeper is reached at. Shared with `setup_coldfront`, which needs to know where the catalog is. |
| `lakekeeper_bind_ip` | Address the Lakekeeper service binds. Defaults to `lakekeeper_host`, and differs only where the bind address is not the reachable one. |
| `lakekeeper_port` | Port Lakekeeper's REST catalog and management API listen on. Shared with `setup_coldfront`. |
| `lakekeeper_metrics_port` | Port for Lakekeeper's Prometheus metrics endpoint. Written into the service environment here. |
| `lakekeeper_warehouse` | Name of the Iceberg warehouse this role creates over the object store. Shared with `setup_coldfront`. |
| `lakekeeper_db` | Name of the private catalog database. |
| `lakekeeper_db_user` | Database role that owns the catalog database. |
| `lakekeeper_db_password` | Password for `lakekeeper_db_user`. |
| `lakekeeper_namespace` | Iceberg namespace pre-created in the warehouse. |
| `coldfront_s3_*` | The S3-compatible object store the warehouse is created over. See the [ColdFront Configuration](../configuration/coldfront.md) reference. |

See the [Configuration Reference](../configuration.md) for descriptions and
defaults.

## How It Works

### Reachability

Both the catalog's own Postgres instance and the object store have to
answer before this role does anything else with them: creating a warehouse
makes Lakekeeper write to the bucket, so a check here turns "the warehouse
create failed" into a named failure with an address attached, rather than a
generic timeout later.

### Health, not just an open port

`/health` is checked rather than the port alone, because a port that merely
accepts connections proves nothing about what is behind it. On a host
where SeaweedFS's own built-in Iceberg REST catalog collides with
Lakekeeper's port, both answer on the same port, and only `/health`'s
response body tells them apart — `pgedge-lakekeeper` 0.13.1 answers unknown
paths with an empty body, while SeaweedFS's Iceberg catalog answers with
a JSON 404.

```json
{"error":{"message":"Path not found","type":"NotFound","code":404}}
```

Getting that body back from `/health` on the expected Lakekeeper host means
the responder is a different service.

!!! warning "Lakekeeper's unit is Type=exec"
    systemd reports a successful start before the process actually binds
    its port. A Lakekeeper that then fails to bind restarts until it trips
    the start limit, and systemd refuses to start it again until that is
    cleared — which is why this role clears any failed unit state before
    starting it.

### Bootstrap and warehouse creation

A first bootstrap answers `204`. A repeat answers `400` with type
`CatalogAlreadyBootstrapped`, which is the only `400` this role accepts;
any other `400` fails the play. The warehouse's storage credential field
names come from the management API of the packaged Lakekeeper 0.13.1
(`S3AccessKeyCredential`) — an older `aws-access-key-id` /
`aws-secret-access-key` spelling exists in some ColdFront documentation,
but this Lakekeeper version does not accept it.

The warehouse request carries the object-store secret, so its output is
hidden. When Lakekeeper refuses the warehouse, the task after it fails
instead, with the HTTP status and Lakekeeper's explanation from the
response body.

When `coldfront_s3_endpoint` is empty, the storage profile leaves out
`endpoint` altogether and uses the `aws` flavor, so Lakekeeper derives
the endpoint from `coldfront_s3_region`. Lakekeeper reads `endpoint` as a
URL, and rejects an empty string with a `422` for the whole request. Any
other endpoint is sent as given, with the `s3-compat` flavor.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/lakekeeper/encryption.key` | New | Encrypts the S3 credential Lakekeeper stores for the warehouse. Generated once; a new key makes existing warehouse secrets unrecoverable. |
| `/etc/lakekeeper/lakekeeper.env` | New | Database DSN, encryption key, bind address, and ports the systemd unit reads. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The
warehouse and namespace creation calls check for an existing entry with
the same name first and skip creation when found. The environment file is
only rewritten, and the service only restarted, when its content actually
changes.

!!! warning "No authorization backend"
    Lakekeeper runs with no authorization backend, so anything that can
    reach `lakekeeper_port` has full use of the catalog API, including
    reading warehouse definitions. Firewall it to the hosts that need it.
