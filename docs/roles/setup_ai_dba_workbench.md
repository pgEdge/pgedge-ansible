# setup_ai_dba_workbench

The `setup_ai_dba_workbench` role configures and starts the pgEdge AI DBA
Workbench on the `ai_dba_workbench` host, and registers every pgEdge
Distributed Postgres node with it to be monitored.

The role performs the following tasks on inventory hosts:

- Create and start the datastore's own Postgres instance: `initdb` into
  `ai_dba_workbench_pg_data`, run by an `ai-dba-workbench-postgres` service
  unit the role writes, listening on `pg_port` at the loopback address only.
  Then create the datastore role, the datastore it owns, and the pgvector
  extension in the datastore, as the Postgres superuser.
- Generate the secret the Workbench encrypts the credentials it stores with,
  once, and write the datastore password and any API keys the language and
  embedding models need into files the services read.
- Write the configuration files of the Workbench's server, collector and
  alerter.
- Enable and start the collector, and wait for it to build the datastore's
  schema; then enable and start the server, and wait for its `/health` to
  report `ok`; then enable and start the alerter. Each service is restarted
  when a file it reads is newer than its running process.
- Generate a self-signed certificate on the controller where the inventory
  names none, write the web client's nginx site, and enable and start nginx.
- Create the Workbench administrator with the server's command-line tool,
  make it a superuser, and sign in as it, giving it the inventory's password
  first where the Workbench refuses that password.
- Register every pgEdge node with the Workbench through its REST API, or bring
  the nodes already registered up to date, and sign out.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `install_ai_dba_workbench` installs the Workbench and the Postgres packages
  for its datastore.
- `setup_ai_dba_workbench_monitor`, on the pgEdge nodes, creates the role the
  Workbench monitors them as, and `setup_postgres` admits this host to them,
  which on an HA cluster `setup_patroni` does through Patroni's configuration.

## When to Use

Execute this role immediately after `install_ai_dba_workbench`, on the same
`ai_dba_workbench` host, once the pgEdge nodes have been built with the
`ai_dba_workbench` group in the inventory and
`setup_ai_dba_workbench_monitor` has run on them. The nodes then hold the
monitoring role and admit this host, so the Workbench's collector can reach
them as soon as they are registered. The
`sample-playbooks/simple-cluster-ai-dba-workbench` and
`sample-playbooks/ultra-ha-ai-dba-workbench` playbooks run it in their last
play:

```yaml
- hosts: ai_dba_workbench
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_ai_dba_workbench
    - setup_ai_dba_workbench
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `ai_dba_workbench_monitor_user` | Role the Workbench logs in to every pgEdge node as. Shared with `setup_ai_dba_workbench_monitor`, which creates it. |
| `ai_dba_workbench_monitor_password` | Password of `ai_dba_workbench_monitor_user`, which this role gives to the Workbench. Declared in `role_config`; set it under `all`. |
| `ai_dba_workbench_db` | Name of the Workbench's datastore. |
| `ai_dba_workbench_db_user` | Database role that owns the datastore and that the Workbench's services log in as. |
| `ai_dba_workbench_db_password` | Password of `ai_dba_workbench_db_user`. Declared in `role_config`, and `init_server` refuses the default or an empty one. |
| `ai_dba_workbench_admin_user` | Name of the Workbench administrator this role creates and signs in as. |
| `ai_dba_workbench_admin_password` | Password of the administrator. Declared in `role_config`, and `init_server` checks it against the Workbench's length limits. |
| `ai_dba_workbench_port` | Port nginx serves the web client, the REST API and the MCP endpoint on, over HTTPS. |
| `ai_dba_workbench_server_port` | Port the Workbench server listens on, on the loopback interface. |
| `ai_dba_workbench_tls_cert_source` | Path on the controller of the certificate nginx serves. Left empty, with `ai_dba_workbench_tls_key_source`, this role generates a self-signed pair. |
| `ai_dba_workbench_tls_key_source` | Path on the controller of that certificate's key. |
| `ai_dba_workbench_llm_provider` | Language model provider for the Workbench's chat and the alerter's reasoning tier. Left empty, the Workbench runs without AI features. |
| `ai_dba_workbench_llm_model` | Language model to use. |
| `ai_dba_workbench_llm_api_key` | API key of the language model's provider. |
| `ai_dba_workbench_llm_base_url` | Address of the language model's API: required for `ollama`, optional for the other providers. |
| `ai_dba_workbench_embedding_provider` | Embedding model provider for the conversation memory and the alerter's second tier. |
| `ai_dba_workbench_embedding_model` | Embedding model to use. |
| `ai_dba_workbench_embedding_api_key` | API key of the embedding model's provider. Defaults to `ai_dba_workbench_llm_api_key` where both name the same provider. |
| `ai_dba_workbench_embedding_base_url` | Address of the embedding model's API. Defaults to `ai_dba_workbench_llm_base_url` where both name the same provider. |
| `ai_dba_workbench_monitor_db` | Database each node is registered with. Left empty, the first database in the node's `db_names`. |
| `ai_dba_workbench_monitor_sslmode` | SSL mode the Workbench connects to the nodes with. |
| `ai_dba_workbench_allowed_hosts` | Further private addresses the Workbench may register, beyond the cluster's own nodes. |
| `ai_dba_workbench_notifications_enabled` | Whether the alerter sends notifications through the channels configured in the web client. |
| `ai_dba_workbench_pg_data` | Data directory of the datastore's Postgres instance. Defaults to `ai-dba-workbench` beside the platform's usual data directories. |
| `pg_port` | Port the datastore's Postgres instance listens on, at the loopback address only. |
| `pg_version` | Major version of the datastore's Postgres instance. |
| `tls_validity_days` | Number of days the self-signed certificate is valid for. |

See the [AI DBA Workbench Configuration](../configuration/ai_dba_workbench.md)
reference for descriptions and defaults.

## How It Works

### The datastore

The Workbench keeps everything it collects in a Postgres instance of its own
on this host, which belongs to this role alone, as the Lakekeeper catalog's
belongs to `setup_lakekeeper`. It is not created by `setup_postgres` and
shares nothing with a pgEdge Distributed Postgres node's: the role initializes
it with `initdb`, with peer authentication over the Unix socket and SCRAM over
TCP, and runs it with a service unit of its own, `ai-dba-workbench-postgres`,
the same way on Debian and RHEL. A changed unit, such as a new `pg_port`,
restarts the instance. The Workbench's server, collector and alerter all
connect to it on `127.0.0.1`, as `ai_dba_workbench_db_user`, with a password.

The packaged units of the collector and the server order themselves after
`postgresql.service`, which is not this instance, so the instance's unit
orders itself before all three of the Workbench's services.

On Debian, installing the server package creates and starts a `main` cluster
on 5432. Where `pg_port` is 5432, the role stops that cluster and marks it
`manual`, so it does not take the port back at boot.

The datastore is owned by `ai_dba_workbench_db_user`, because the collector
builds the datastore's schema when it starts: tables in `public`, which on
Postgres 15 and later only a database's owner may create objects in by default,
and a schema of its own for the metrics.

The collector creates pgvector's `vector` extension in the datastore itself,
but only in its first migration, and only where it is allowed to, which takes a
superuser. Otherwise it continues without the extension and never tries again,
and the alerter's second tier and the conversation memory go without it. This
role creates the extension as the Postgres superuser before the collector first
starts, so that `ai_dba_workbench_db_user` needs no further privilege.

### The secret and the files the services read

The Workbench server encrypts the passwords of the servers it monitors, and
the credentials of the notification channels configured in the web client,
with a secret, and the collector and the alerter decrypt them with the same
secret. All three read it from `/etc/pgedge/ai-dba.secret`, which this role
generates once, with `openssl rand -base64 32`, and keeps.

The services cannot write to `/etc` themselves, so this role writes every
file they read there beforehand:

- The datastore password, in `/etc/pgedge/ai-dba-db.password`.
- The language model's API key, in `/etc/pgedge/ai-dba-llm.key`, where
  `ai_dba_workbench_llm_provider` is `anthropic`, `openai` or `gemini`.
- The embedding model's API key, in `/etc/pgedge/ai-dba-embedding.key`, where
  `ai_dba_workbench_embedding_provider` is `openai`, `gemini` or `voyage`.

Each of these belongs to the `pgedge` user the services run as, and nobody
else can read it, because the Workbench warns about a secret that others
can read. A key file is written, and named in the configuration, only for a
provider that is set: the Workbench server refuses to start with a key file
it cannot read, even one for a provider it does not use. A key file that no
configured provider uses any more is removed.

The three configuration files, `/etc/pgedge/ai-dba-server.yaml`,
`/etc/pgedge/ai-dba-collector.yaml` and `/etc/pgedge/ai-dba-alerter.yaml`,
name these files rather than holding their contents, so they hold no secret.
This role writes them over the packaged files, owned by `root` and readable
by the `pgedge` group, as the packages install them. The Workbench's own
defaults apply to every setting they leave out.

!!! warning "Keep the Workbench's secret"
    A new secret leaves every password the Workbench has stored unreadable,
    so this role never replaces `/etc/pgedge/ai-dba.secret`. If the file is
    lost, the next run generates a new one and gives every registered node
    its password again, which the server, restarted on the new secret,
    encrypts with it. The credentials of the notification channels, which
    the role does not know, have to be entered again in the web client.

### Start order

The packages enable and start none of the Workbench's services. This role
starts the collector first, because the collector creates and migrates the
datastore's schema when it starts, and the server exits at once, without
retrying, if it finds no schema or one older than it needs. The role then
waits, for up to a minute, until the datastore's `schema_version` table
records version 4 at least, which is the oldest the server accepts.

The server is started next. It only starts listening once it has reached the
datastore and found its schema, so the role waits, for up to a minute, for `GET
/health` on `127.0.0.1:ai_dba_workbench_server_port` to answer with a status of
`ok`. The body is checked as well as the status code, because a port that
answers proves nothing about which service is behind it. The alerter is started
last.

### Restarts

Whether a service is restarted is decided by when it last started, as
`setup_lakekeeper` decides for Lakekeeper, rather than by whether this run
changed one of its files. A file newer than the running process is one the
service has not read, so a run that wrote a file and failed before the
restart is caught by the next run. The start time is accurate to a second,
and that second is allowed for. A service with no running process reads as
never started, and is restarted.

| Service | Files it is restarted for |
|---------|---------------------------|
| `pgedge-ai-dba-collector` | Its configuration, the secret, and the datastore password. |
| `pgedge-ai-dba-server` | Its configuration, the secret, the datastore password, and the API key files in use. |
| `pgedge-ai-dba-alerter` | Its configuration, the secret, the datastore password, and the API key files in use. |
| `nginx` | The web client's site, its certificate, and its key. |

### The web client

nginx serves the web client over HTTPS on `ai_dba_workbench_port`, and proxies
the REST API, under `/api/`, and the MCP endpoint, under `/mcp/`, to the
Workbench server. The server listens on `127.0.0.1` alone, so other hosts reach
it only through nginx. It trusts `127.0.0.1` as a proxy, so it takes a
browser's address from the `X-Forwarded-For` header nginx adds, rather than
taking nginx's own address. Both proxied locations allow 90 seconds for a
response, as the packaged site does, for a language model's slow answers and
long-running queries.

A request sent to `ai_dba_workbench_port` over plain HTTP gets nginx's own
`497` error, which the site turns into a `301` redirect to the same address
over HTTPS.

The certificate is the one `ai_dba_workbench_tls_cert_source` and
`ai_dba_workbench_tls_key_source` name on the controller. Where they are empty,
this role generates a self-signed pair on the controller, in
`tls/ai-dba-workbench`, which Ansible resolves against the playbook's own
directory, the way `setup_postgres` stages the nodes' certificates. The
certificate's names are the host's name, its fully qualified name, its default
IPv4 address and its inventory name, and it is valid for `tls_validity_days`.
Either pair is copied to `/etc/pgedge/ai-dba-client.crt` and
`/etc/pgedge/ai-dba-client.key`.

The site sends a `Strict-Transport-Security` header only with a certificate
from the inventory. A browser that has seen that header refuses a
self-signed certificate outright, rather than offering to continue past it.

This role writes its site over the file the `pgedge-ai-dba-client` package
installs, rather than beside it, because the Debian package enables its own
site again whenever it is upgraded, and a second site would listen beside
this one. On Debian the role also keeps the package's link to the site in
`/etc/nginx/sites-enabled`. It checks the whole configuration with
`nginx -t` before nginx is started or restarted on it, and then waits for
`https://127.0.0.1:ai_dba_workbench_port/` to answer, without verifying the
certificate.

!!! note "A self-signed certificate"
    Browsers warn about the generated certificate until it is trusted. Set
    `ai_dba_workbench_tls_cert_source` and `ai_dba_workbench_tls_key_source` to
    a certificate from an authority the browsers already trust to avoid the
    warning.

### The administrator

The administrator is the account this role registers the nodes as, and the
account to sign in to the web client with. The role creates it with the
Workbench server's own command-line tool, `/usr/bin/ai-dba-server`, which
manages the users in the server's user store, under
`/var/lib/pgedge/ai-dba-server`. The tool runs as the `pgedge` user, so that
every file of the store stays that user's, and is given the store's
directory, since without it the tool would open a new, empty store beside its
binary.

The tool reads a password only from a file or a terminal. Where the
administrator does not exist yet, the role writes the password to
`/var/lib/pgedge/ai-dba-server/.admin-password`, readable by the `pgedge`
user alone, runs `-add-user`, and removes the file again whether the tool
succeeded or not. Registering a server takes a superuser, and the tool cannot
report whether a user is one, so the role runs `-set-superuser` on every
pass, which changes nothing where the administrator already is one.

The role then signs in, with `POST /api/v1/auth/login`. The Workbench keeps
no other way of telling whether the administrator's password is the
inventory's, so a sign-in it refuses with `401` is taken to mean the password
has changed: the role sets the inventory's password with `-update-user`,
through the same file, and signs in again. A password changed in the web
client is therefore changed back on the next run. A refused sign-in counts
towards the Workbench's lockout, which disables an account after ten refused
sign-ins in a row, and a run whose password has changed causes one. When the
second sign-in is refused as well, as it is for an account the lockout has
disabled, the run fails with a message that names the command that enables
the account again.

The sign-in requests carry the password, so their output is hidden. They
record their outcome rather than failing, and a task after them reports the
HTTP status and the Workbench's explanation when the sign-in did not
succeed. The session lives only as long as the server process, and the role
signs out when it is done with it.

### Registering the nodes

Each pgEdge node is registered under its inventory name, at the address its
facts give, on its own `pg_port`: directly, rather than through HAProxy or
pgBouncer, so that the Workbench sees each member of an HA zone separately
and works out the cluster's replication topology for itself. The record
holds:

- The description `pgEdge Distributed Postgres node in zone <zone> of
  cluster <cluster_name>`.
- The database `ai_dba_workbench_monitor_db`, or the first database in the
  node's own `db_names` where that is empty. The collector reads every other
  database on the node as well.
- The user `ai_dba_workbench_monitor_user` and its password, and the SSL mode
  `ai_dba_workbench_monitor_sslmode`.
- Monitored, so the collector reads the node, and shared with the
  Workbench's other users rather than kept to the administrator.

A node's own settings come from its hostvars, falling back to this host's
where the inventory set none for it, because the `pgedge` group's variables
do not reach this host.

The Workbench accepts a name of at most 255 characters made of letters,
digits, spaces, and the characters `.`, `_`, `(`, `)` and `-`. It refuses a
node whose inventory name holds any other character, such as the colons of
an IPv6 address, and the run reports the refusal.

The Workbench server refuses to register a private or loopback address that
it is not told to allow. The role writes every node's address, and each
entry of `ai_dba_workbench_allowed_hosts`, into the server's
`connection_security.allowed_hosts`, and leaves private networks closed to
everything else.

The role lists the servers the Workbench has registered, and reads each node
already registered in full, since the list leaves out each server's user name
and SSL mode. A node that is not registered is created with
`POST /api/v1/connections`. A registered node whose record differs from the
inventory is updated with `PUT /api/v1/connections/<id>`, with the fields
that differ; the Workbench keeps every field an update leaves out.

The Workbench never returns a password it has stored, so the role keeps a
SHA-256 digest of the monitoring passwords it last gave the Workbench in
`/etc/pgedge/ai-dba-monitor.sha256`, on the host that already holds the
secret the Workbench encrypts the passwords themselves with. Where the
inventory's passwords no longer match the digest, or there is no digest yet,
or the run generated a new secret, every registered node is given its
password again. The digest is written only once every node has been created
or updated, so a run that failed part of the way through leaves the next run
to give the passwords again.

The requests that carry a password hide their output, and record their
outcome rather than failing; the task after each reports the node, the HTTP
status, and the Workbench's explanation of a refusal.

A node the inventory no longer lists stays registered. The Workbench cannot
tell the servers this role registered from those registered in the web
client, so the role removes none of them. Remove such a node in the web
client.

### On the pgEdge nodes

Where the inventory has an `ai_dba_workbench` host, the pgEdge nodes are
prepared for the Workbench. `setup_ai_dba_workbench_monitor` installs the
`system_stats` extension and creates `ai_dba_workbench_monitor_user` and the
extensions and grants the Workbench's probes need, and the nodes admit this
host as that role. The section [What the
Nodes Are Given](../configuration/ai_dba_workbench.md#what-the-nodes-are-given)
of the configuration reference describes each of these.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/systemd/system/ai-dba-workbench-postgres.service` | New | Runs the datastore's Postgres instance. |
| `ai_dba_workbench_pg_data` | New | The datastore's Postgres data directory. |
| `/etc/pgedge/ai-dba.secret` | New | The secret the Workbench encrypts stored credentials with. Generated once and kept. |
| `/etc/pgedge/ai-dba-db.password` | New | The datastore password the services read. |
| `/etc/pgedge/ai-dba-llm.key` | New | The language model's API key, only where its provider needs one. |
| `/etc/pgedge/ai-dba-embedding.key` | New | The embedding model's API key, only where its provider needs one. |
| `/etc/pgedge/ai-dba-server.yaml` | Modified | The Workbench server's configuration. |
| `/etc/pgedge/ai-dba-collector.yaml` | Modified | The collector's configuration. |
| `/etc/pgedge/ai-dba-alerter.yaml` | Modified | The alerter's configuration. |
| `/etc/pgedge/ai-dba-client.crt` | New | The certificate nginx serves the web client with. |
| `/etc/pgedge/ai-dba-client.key` | New | The key of that certificate. |
| `/etc/nginx/sites-available/pgedge-ai-dba-client` (Debian), `/etc/nginx/conf.d/pgedge-ai-dba-client.conf` (RHEL) | Modified | The web client's nginx site. |
| `/etc/pgedge/ai-dba-monitor.sha256` | New | A digest of the monitoring passwords the Workbench was last given. |
| `tls/ai-dba-workbench/server.key`, `server.csr`, `server.crt` on the controller | New | The self-signed pair, only where the inventory names no certificate. |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The secret is
generated only when it does not exist, and the files and templates are only
rewritten when their content changes; a service is only restarted when one of
its files is newer than its running process. The administrator is created
only when it is missing, and its password changed only when the Workbench
refuses the inventory's. A node is registered only when it is missing, and
updated only where its record differs from the inventory or the monitoring
passwords have changed.

The end-to-end tests apply `install_ai_dba_workbench` and
`setup_ai_dba_workbench` a second time after the deployment, and fail if any
task reports a change.
