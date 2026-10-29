# AI DBA Workbench Configuration

The pgEdge AI DBA Workbench is a monitoring and AI-assisted management tool for
PostgreSQL. Its collector reads statistics from every server it is given into a
datastore of its own, its alerter raises alerts from what the collector
records, and its server serves the REST API the web client uses, an MCP
endpoint, and, where a language model is configured, the Workbench's chat. The
`install_ai_dba_workbench` and `setup_ai_dba_workbench` roles make one
dedicated host, the only member of the `ai_dba_workbench` group, the Workbench,
and register every pgEdge Distributed Postgres node with it.

The Workbench runs on one host whatever the size of the cluster or its number
of zones. Its collector, server and alerter share one datastore, which
`setup_ai_dba_workbench` keeps in a Postgres instance of its own on that host,
and one secret that encrypts the credentials they store. `init_server` refuses
an `ai_dba_workbench` group of more than one host, and a host that is in both
the `pgedge` and `ai_dba_workbench` groups. The web client is served at
`https://<the Workbench host>:8444`, where the administrator, `admin` by
default, signs in with `ai_dba_workbench_admin_password`.

The Workbench is optional, so its sample playbooks and inventories are kept
apart from the plain ones. The
`sample-playbooks/simple-cluster-ai-dba-workbench` and
`sample-playbooks/ultra-ha-ai-dba-workbench` playbooks are the plain ones with
`setup_ai_dba_workbench_monitor` after `setup_pgedge`, so that every database
it prepares exists by then, and a play for the Workbench at the end.
That play runs `install_ai_dba_workbench` and `setup_ai_dba_workbench` on the
`ai_dba_workbench` group, because `setup_ai_dba_workbench` registers the nodes
the earlier plays build. The two playbooks need an inventory with an
`ai_dba_workbench` host, and `setup_ai_dba_workbench_monitor` stops without
one; a cluster without the Workbench is deployed from the plain playbooks.

The simple-cluster and Ultra-HA end-to-end tests cover the Workbench with a
host of its own and no language model. To run that variant locally, pass
`ai-dba-workbench` after the operating system:

```bash
./tests/run-test.sh simple-cluster debian12 ai-dba-workbench
./tests/run-test.sh ultra-ha debian12 ai-dba-workbench
```

## Trying the Workbench in Containers

The test suite's Docker Compose files start hosts for a cluster with the
Workbench as systemd containers, which a sample playbook then deploys to over
SSH like any other hosts, without hosts of your own. The roles install every
pgEdge and Workbench package from the pgEdge package repository, as they would
on virtual machines, rather than from the Workbench's release tarballs or
container images. It needs a Linux host with Docker, the Compose plugin and
Ansible, and is run from the top of a checkout.

First, create the SSH key the containers accept, which the image build copies
in from `tests/docker/authorized_keys`:

```bash
mkdir -p tests/.ssh
[ -f tests/.ssh/id_ed25519 ] || \
  ssh-keygen -t ed25519 -f tests/.ssh/id_ed25519 -N "" -q
cp tests/.ssh/id_ed25519.pub tests/docker/authorized_keys
```

Then, start the containers. The scenario's compose file starts the pgEdge
nodes and a client host on a Docker network, 192.168.6.0/24, and the Workbench
overlay adds the Workbench host at 192.168.6.33:

```bash
docker compose -p pgedge-workbench \
  -f tests/compose/simple-cluster-debian12.yml \
  -f tests/compose/ai-dba-workbench-debian12.yml up -d --build
```

Then, build and install the collection from the checkout, and run the
Workbench's sample playbook with the scenario's inventory and the Workbench
layer over it:

```bash
make install
ANSIBLE_CONFIG=tests/ansible.cfg ansible-playbook \
  -i tests/inventories/simple-cluster.yml \
  -i tests/inventories/ai-dba-workbench.yml \
  --private-key tests/.ssh/id_ed25519 \
  sample-playbooks/simple-cluster-ai-dba-workbench/playbook.yaml
```

The web client is then at `https://192.168.6.33:8444` from the Docker host.
Sign in as `admin` with the `ai_dba_workbench_admin_password` that
`tests/inventories/ai-dba-workbench.yml` sets, and accept the self-signed
certificate. No language model is configured, so the Workbench monitors and
alerts with its AI features off. Running the playbook again changes only what
differs. The following command removes the containers and their volumes:

```bash
docker compose -p pgedge-workbench \
  -f tests/compose/simple-cluster-debian12.yml \
  -f tests/compose/ai-dba-workbench-debian12.yml down -v
```

For two zones under Patroni, use `tests/compose/ultra-ha-debian12.yml`,
`tests/inventories/ultra-ha.yml` and
`sample-playbooks/ultra-ha-ai-dba-workbench/playbook.yaml` instead, which run
twelve containers; each systemd container takes several inotify instances, so
raise `fs.inotify.max_user_instances` if containers fail to start. Each
compose file and Workbench overlay is also there for `debian13`, `ubuntu2404`,
`ubuntu2604` and `rocky9`. Of those, `ubuntu2404` needs `ansible-core` 2.16 or
later, `debian13` 2.18 or later and `ubuntu2604` 2.20 or later, rather than
the 2.14 that Debian 12 ships, as [Installation](../installation.md)
describes.

`tests/run-test.sh simple-cluster debian12 ai-dba-workbench --keep` does all
of this in one command, runs the end-to-end test's checks as well, and leaves
the containers running; its last line gives the command that removes them.

## What the Nodes Are Given

Where the inventory has an `ai_dba_workbench` host,
`setup_ai_dba_workbench_monitor` prepares the pgEdge nodes for the Workbench,
and `setup_postgres`, or `setup_patroni` on an HA cluster, admits the
Workbench host. `role_config`
answers whether the inventory has one in `ai_dba_workbench_enabled`, from the
`ai_dba_workbench` group itself, so every host agrees on it.

- `setup_ai_dba_workbench_monitor` installs the `system_stats` extension on
  every node, replicas included, since the Workbench monitors each member
  directly: the `pgedge-postgresql-<ver>-system-stats` package on Debian and
  `pgedge-system_stats_<ver>` on RHEL.
- `setup_ai_dba_workbench_monitor` creates `ai_dba_workbench_monitor_user`, a
  login role with `ai_dba_workbench_monitor_password`. It is a member of
  `pg_monitor`, which reads the statistics views, every setting, and the query
  text in `pg_stat_statements`, and of `monitor_system_stats`, the role the
  `system_stats` extension grants its functions to. It is not a superuser.
- `setup_ai_dba_workbench_monitor` creates the `pg_stat_statements` and
  `system_stats` extensions in each database in `db_names`, `postgres`, and
  `coldfront_db` where `coldfront_enabled` is set. In each of them it also
  grants `SELECT` on `pg_hba_file_rules` and `pg_ident_file_mappings`, and
  `EXECUTE` on the functions behind them, which Postgres otherwise restricts to
  superusers. A grant on a system view belongs to the database it is made in.
- In each database in `db_names`, `setup_ai_dba_workbench_monitor` grants
  `USAGE` on the `spock` schema, and `SELECT` on `spock.node`,
  `spock.local_node`, `spock.subscription`, `spock.exception_log` and
  `spock.resolutions`, which the Workbench reads to place each node in the
  cluster's topology and to report replication errors.
- The nodes admit the Workbench host, as `ai_dba_workbench_monitor_user`, to
  every database, with a `scram-sha-256` password. The rule is `role_config`'s
  `pg_ai_dba_workbench_hba_rules`, one of the `pg_required_hba_rules` that
  `setup_postgres` writes into `pg_hba.conf` on a simple cluster, and that
  `setup_patroni` writes into Patroni's configuration on an HA cluster, from
  which Patroni writes `pg_hba.conf`.

In an HA zone, `setup_ai_dba_workbench_monitor` creates the role, the
extensions and the grants on the zone's leader, and the replicas receive them
through physical replication. Every statement runs with Spock's DDL
replication off for its session: by the time the role runs, each database in
`db_names` is in Spock, and each node creates these objects itself, so a
replicated copy of a statement would arrive at nodes that already hold the
object.

The Workbench can be added to a running cluster by putting a host in the
`ai_dba_workbench` group and running the playbook again. The run writes the
new access rule on every node, but a node that is already running reads it
only when it is reloaded or restarted, so reload each node once the run
completes. On a simple cluster:

```bash
sudo -u postgres psql -c 'SELECT pg_reload_conf()'
```

On an HA cluster, Patroni rewrites `pg_hba.conf` from its configuration file
and reloads Postgres when it is told to reload. Run this on each member,
substituting the cluster's `patroni_scope`, such as `17-demo`, and the
member's host name. The file is `/etc/patroni/patroni.yml` on RHEL and
`/etc/patroni/<pg_version>-<cluster_name>.yml`, such as `17-demo.yml`, on
Debian:

```bash
sudo -u postgres patronictl -c /etc/patroni/patroni.yml reload --force <scope> <member>
```

`pg_stat_statements` also needs its library preloaded, which the collection
does unless the inventory sets `shared_preload_libraries` to null in
`pg_parameters`. Without the library the extension exists, and its view
refuses every query the Workbench makes.

## Inventory Example

The monitoring role's password goes under `all`, because the `pgedge` group
creates the role and the `ai_dba_workbench` group gives its password to the
Workbench. In the following example, the inventory retrieves every password
from Ansible Vault:

```yaml
all:
  vars:
    ai_dba_workbench_monitor_password: "{{ vault_ai_dba_workbench_monitor_password }}"

ai_dba_workbench:
  vars:
    ai_dba_workbench_db_password: "{{ vault_ai_dba_workbench_db_password }}"
    ai_dba_workbench_admin_password: "{{ vault_ai_dba_workbench_admin_password }}"
  hosts:
    192.168.6.21:
```

## Shared Parameters

The following parameters are defined in `role_config`, because more than one
role reads them or `init_server` checks them.

### ai_dba_workbench_monitor_user

- Type: String
- Default: `ai_dba_workbench_monitor`
- Description: Role the Workbench logs in to every pgEdge node as.
  `setup_ai_dba_workbench_monitor` creates it on the nodes, the nodes admit the
  Workbench host as it, and `setup_ai_dba_workbench` registers each node with
  it. A node's own
  value, where its hostvars set one, is the one registered for that node.

### ai_dba_workbench_monitor_password

- Type: String
- Default: `secret`
- Description: Password for `ai_dba_workbench_monitor_user`. `init_server`
  refuses to run while it is empty or still the default, on the pgEdge nodes
  where the inventory has an `ai_dba_workbench` host and on the Workbench host,
  so set it under `all`. When it changes, the next run gives every registered
  node the new password.

### ai_dba_workbench_db_password

- Type: String
- Default: `secret`
- Description: Password for `ai_dba_workbench_db_user`, the role the
  Workbench's services log in to their datastore as. `init_server` refuses to
  run while it is empty or still the default.

### ai_dba_workbench_admin_password

- Type: String
- Default: `secret`
- Description: Password of the Workbench administrator,
  `ai_dba_workbench_admin_user`. The Workbench refuses a password shorter than
  12 characters or longer than 72 bytes, which `init_server` checks before
  anything is installed, and one on its own list of common passwords, which
  only the Workbench can check, so that refusal comes from
  `setup_ai_dba_workbench`. `init_server` also refuses the default. A changed
  password reaches the Workbench on the next run.

### ai_dba_workbench_port

- Type: Integer
- Default: `8444`
- Description: Port nginx listens on, over HTTPS. It serves the web client
  there, and passes requests under `/api/` and `/mcp/` on to the Workbench
  server's REST API and MCP endpoint. A plain HTTP request to the port is
  redirected to HTTPS. `init_server` refuses a port that collides with
  `ai_dba_workbench_server_port` or `pg_port` on the Workbench host.

### ai_dba_workbench_server_port

- Type: Integer
- Default: `8443`
- Description: Port the Workbench server listens on, on the loopback interface
  alone, behind nginx. `setup_ai_dba_workbench` calls the REST API there.
  `init_server` refuses a port that collides with `ai_dba_workbench_port` or
  `pg_port`.

### ai_dba_workbench_tls_cert_source

- Type: String
- Default: `""`
- Description: Path on the controller of the certificate nginx serves the web
  client with. Left empty, together with `ai_dba_workbench_tls_key_source`,
  `setup_ai_dba_workbench` generates a self-signed pair on the controller, in
  `tls/ai-dba-workbench` beside the playbook, which browsers warn about until
  it is trusted. With a certificate from the inventory, the web client also
  sends a `Strict-Transport-Security` header.

### ai_dba_workbench_tls_key_source

- Type: String
- Default: `""`
- Description: Path on the controller of the key of
  `ai_dba_workbench_tls_cert_source`. `init_server` refuses one of the two
  without the other.

In the following example, the inventory supplies a certificate from the
controller:

```yaml
ai_dba_workbench:
  vars:
    ai_dba_workbench_tls_cert_source: /etc/ssl/workbench/workbench.crt
    ai_dba_workbench_tls_key_source: /etc/ssl/workbench/workbench.key
```

## Language and Embedding Model Parameters

The Workbench's AI features are optional. Without a language model or an
embedding model it runs as a monitoring and alerting tool, and its alerter
uses its statistical first tier alone. `init_server` checks the settings of
each model that is set: the provider has to be one the Workbench supports for
that model, the model has to be named, and every provider but `ollama` needs
an API key, while `ollama` needs the address of its API instead.

`setup_ai_dba_workbench` writes an API key to a file, and names the file in the
Workbench's configuration, only for a provider that needs one. The file
belongs to the `pgedge` user the Workbench's services run as, and only that
user can read it.

### ai_dba_workbench_llm_provider

- Type: String
- Default: `""`
- Description: Provider of the language model behind the Workbench's chat and
  the alerter's third, reasoning tier: `anthropic`, `openai`, `gemini` or
  `ollama`. Left empty, the server's configuration has no language model, and
  the alerter's third tier is off.

### ai_dba_workbench_llm_model

- Type: String
- Default: `""`
- Description: Name of the language model, which the server uses for the
  chat and the alerter for its reasoning tier. Required once
  `ai_dba_workbench_llm_provider` is set.

### ai_dba_workbench_llm_api_key

- Type: String
- Default: `""`
- Description: API key of the language model's provider, written to
  `/etc/pgedge/ai-dba-llm.key`. Required for `anthropic`, `openai` and
  `gemini`.

### ai_dba_workbench_llm_base_url

- Type: String
- Default: `""`
- Description: Address of the language model's API. Required for `ollama`,
  where it becomes the server's `ollama_url`. For the other providers it is
  optional, and points the Workbench at another endpoint than the provider's
  own, such as an OpenAI-compatible proxy.

### ai_dba_workbench_embedding_provider

- Type: String
- Default: `""`
- Description: Provider of the embedding model behind the Workbench's
  conversation memory and the alerter's second tier, which compares an
  anomaly with ones it has seen before: `openai`, `gemini`, `voyage` or
  `ollama`, since Anthropic offers no embeddings. Left empty, the server's
  configuration has no embedding model, and the alerter's second tier is off.

### ai_dba_workbench_embedding_model

- Type: String
- Default: `""`
- Description: Name of the embedding model. Required once
  `ai_dba_workbench_embedding_provider` is set.

### ai_dba_workbench_embedding_api_key

- Type: String
- Default: `ai_dba_workbench_llm_api_key` where
  `ai_dba_workbench_embedding_provider` is the same as
  `ai_dba_workbench_llm_provider`, and `""` otherwise
- Description: API key of the embedding model's provider, written to
  `/etc/pgedge/ai-dba-embedding.key`. Required for `openai`, `gemini` and
  `voyage`.

### ai_dba_workbench_embedding_base_url

- Type: String
- Default: `ai_dba_workbench_llm_base_url` where
  `ai_dba_workbench_embedding_provider` is the same as
  `ai_dba_workbench_llm_provider`, and `""` otherwise
- Description: Address of the embedding model's API. Required for `ollama`,
  optional for the other providers.

In the following example, the inventory gives the Workbench Anthropic's
language model and OpenAI's embeddings, with both keys from Ansible Vault:

```yaml
ai_dba_workbench:
  vars:
    ai_dba_workbench_llm_provider: anthropic
    ai_dba_workbench_llm_model: claude-sonnet-4-5
    ai_dba_workbench_llm_api_key: "{{ vault_anthropic_api_key }}"
    ai_dba_workbench_embedding_provider: openai
    ai_dba_workbench_embedding_model: text-embedding-3-small
    ai_dba_workbench_embedding_api_key: "{{ vault_openai_api_key }}"
```

In the following example, both models are served by Ollama. The embedding
model takes the language model's address, since both name the same provider:

```yaml
ai_dba_workbench:
  vars:
    ai_dba_workbench_llm_provider: ollama
    ai_dba_workbench_llm_model: qwen2.5:7b-instruct
    ai_dba_workbench_llm_base_url: http://192.168.6.40:11434
    ai_dba_workbench_embedding_provider: ollama
    ai_dba_workbench_embedding_model: nomic-embed-text
```

## Workbench Host Parameters

The following parameters are `setup_ai_dba_workbench`'s own defaults, which
only the Workbench host reads.

### ai_dba_workbench_db

- Type: String
- Default: `ai_workbench`
- Description: Name of the Workbench's datastore, in the Postgres instance
  `setup_ai_dba_workbench` creates on the Workbench host for it alone.

### ai_dba_workbench_db_user

- Type: String
- Default: `ai_workbench`
- Description: Database role that owns the datastore, and that the
  Workbench's server, collector and alerter log in as.

### ai_dba_workbench_admin_user

- Type: String
- Default: `admin`
- Description: Name of the Workbench administrator, which
  `setup_ai_dba_workbench` creates and registers the nodes as, and which signs
  in to the web client.

### ai_dba_workbench_monitor_db

- Type: String
- Default: `""`
- Description: Database each node is registered with: the one the
  Workbench's tools query, and the one its probes of the server as a whole
  run in. Left empty, each node is registered with the first database in its
  own `db_names`. The collector reads every other database on the node as
  well.

### ai_dba_workbench_monitor_sslmode

- Type: String
- Default: `require`
- Description: SSL mode the Workbench connects to the nodes with. `require`
  encrypts the connection with the certificate `setup_postgres` gives every
  node, which is self-signed, so it cannot be verified against an authority.

### ai_dba_workbench_allowed_hosts

- Type: List
- Default: `[]`
- Description: Further addresses the Workbench may register although they are
  private. The Workbench refuses a private or loopback address it is not told
  to allow, and `setup_ai_dba_workbench` tells it to allow the cluster's own
  nodes. List here any other server on a private network that is to be
  registered through the web client. Each entry is an address, a CIDR range, or
  an exact host name.

### ai_dba_workbench_notifications_enabled

- Type: Boolean
- Default: `true`
- Description: Whether the alerter sends notifications through the channels
  configured in the web client, whose credentials it decrypts with the
  Workbench's secret.

### ai_dba_workbench_pg_data

- Type: String
- Default: `{{ pg_home }}/{{ pg_version }}/ai-dba-workbench`
- Description: Data directory of the datastore's own Postgres instance, which
  `setup_ai_dba_workbench` creates and runs as the
  `ai-dba-workbench-postgres` service.

The datastore's Postgres instance takes `pg_version` and `pg_port`, as a
pgEdge node's does, and listens on `pg_port` at the loopback address only. See
[setup_ai_dba_workbench](../roles/setup_ai_dba_workbench.md) for what the role does with each of
these settings.
