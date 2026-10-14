# setup_lakekeeper

The `setup_lakekeeper` role configures Lakekeeper's catalog database, starts
the service, and bootstraps the Iceberg warehouse and namespace ColdFront
commits through.

The role performs the following tasks on inventory hosts:

- Create and start the catalog's own Postgres instance, with
  `setup_postgres`'s `plain_instance` task file, the same tasks that create
  a pgEdge Distributed Postgres node's instance.
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
- Enable and start the `lakekeeper` service, and restart it when its
  environment file is newer than the running process.
- Wait for `/health` to report `ok`, rather than for the port alone to
  accept connections.
- Bootstrap the catalog, create the warehouse over the object store or
  bring an existing warehouse's storage profile up to date, and pre-create
  the Iceberg namespace.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_lakekeeper` installs the Lakekeeper and Postgres packages.
- `setup_postgres` provides the tasks that create the catalog's Postgres
  instance.

## When to Use

Execute this role immediately after `install_lakekeeper`, on the same
dedicated `lakekeeper` host, which `init_server` has prepared and checked
like every other host.

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
| `lakekeeper_db_password` | Password for `lakekeeper_db_user`. Declared in `role_config`, and `init_server` refuses the default. |
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

### Keeping the warehouse up to date

On a later run the warehouse already exists, and the role compares the
storage profile Lakekeeper reports for it with the one the inventory
describes: the bucket, region, path-style addressing, flavor and endpoint.
Where any differ, it sends the whole profile again, with the credential,
since Lakekeeper removes a warehouse's credential when an update leaves it
out. Lakekeeper checks the new profile by writing to the bucket, as it does
on create, and refuses a changed bucket, or a changed region without an
endpoint, rather than lose the data the warehouse holds. The task after the
update reports a refusal with Lakekeeper's explanation.

Lakekeeper never returns a stored credential, so a change to
`coldfront_s3_access_key` or `coldfront_s3_secret_key` alone is not
detected and does not reach the warehouse. The pgEdge nodes take the new
credential on their next run of `setup_coldfront`.

### Restarts

Whether Lakekeeper is restarted is decided by when it last started, as
`setup_etcd` decides for etcd, not by whether this run changed its
environment file. An environment file newer than the running process is
one Lakekeeper has not read, so a run that wrote the file and failed before
the restart is caught by the next run.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/lakekeeper/encryption.key` | New | Encrypts the S3 credential Lakekeeper stores for the warehouse. Generated once; a new key makes existing warehouse secrets unrecoverable. |
| `/etc/lakekeeper/lakekeeper.env` | New | Database DSN, encryption key, bind address, and ports the systemd unit reads. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The
warehouse and namespace creation calls check for an existing entry with
the same name first and skip creation when found. An existing warehouse's
storage profile is updated only where it differs from the inventory. The
environment file is only rewritten when its content changes, and the
service only restarted when that file is newer than the running process.

!!! warning "No authorization backend"
    Lakekeeper runs with no authorization backend, so anything that can
    reach `lakekeeper_port` has full use of the catalog API, including
    reading warehouse definitions. Firewall it to the hosts that need it.
