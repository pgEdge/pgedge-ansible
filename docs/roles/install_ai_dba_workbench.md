# install_ai_dba_workbench

The `install_ai_dba_workbench` role installs the pgEdge AI DBA Workbench, a
monitoring and AI-assisted management tool for the cluster, along with the
Postgres packages for the Workbench's own datastore, which
`setup_ai_dba_workbench` creates. The Workbench host is not a pgEdge
Distributed Postgres node: its Postgres instance holds the Workbench's own data
and never runs Spock.

The role performs the following tasks on inventory hosts:

- Install the Workbench's four packages: `pgedge-ai-dba-server`,
  `pgedge-ai-dba-collector`, `pgedge-ai-dba-alerter`, and
  `pgedge-ai-dba-client`.
- Install the Postgres server package for `pg_version`, the matching pgvector
  package, and `pgedge-python3-psycopg2`.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares the host and checks the inventory, including the
  Workbench's passwords and that the host's ports do not collide.
- `install_repos` configures pgEdge package repositories.

## When to Use

Execute this role on the one host in the `ai_dba_workbench` group, separate
from every pgEdge Distributed Postgres node. `init_server` refuses a host that
is in both the `pgedge` and `ai_dba_workbench` groups, and an
`ai_dba_workbench` group of more than one host: the Workbench's collector,
server and alerter share one datastore and one secret on that host.

```yaml
- hosts: ai_dba_workbench
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_ai_dba_workbench
    - setup_ai_dba_workbench
```

Apply `init_server` to the Workbench host first, as to every host. The
`sample-playbooks/simple-cluster-ai-dba-workbench` playbook does so in the
same play, and `sample-playbooks/ultra-ha-ai-dba-workbench` in its first play,
which runs it on every host.
Both playbooks run the Workbench's play last, after the pgEdge nodes are built
and `setup_ai_dba_workbench_monitor` has run on them, because
`setup_ai_dba_workbench` registers the nodes with the Workbench:

```yaml
- hosts: ai_dba_workbench
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    - install_ai_dba_workbench
    - setup_ai_dba_workbench
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `pg_version` | Major version of the Postgres instance installed here for the Workbench's datastore, and of the pgvector package installed with it. |

The settings the Workbench runs on, such as its ports, its passwords and its
language model, belong to [setup_ai_dba_workbench](setup_ai_dba_workbench.md#configuration).

See the [AI DBA Workbench Configuration](../configuration/ai_dba_workbench.md)
reference for descriptions and defaults.

## How It Works

1. Installs the four Workbench packages from the pgEdge package repository
   that `install_repos` configures, rather than the `.tar.gz` archives
   attached to the Workbench's releases on GitHub. The collector, the alerter
   and the web client each require the server package at the same version, so
   all four come from one release, and the web client requires nginx, which
   the package manager installs with it from the distribution's repositories.
   The server package creates the `pgedge` system user and group the
   Workbench's services run as.
2. Installs the Postgres package matching `pg_version`, the pgvector package,
   and `pgedge-python3-psycopg2`, which the `community.postgresql` modules in
   `setup_ai_dba_workbench` need. The collector creates pgvector's extension in
   the datastore for the alerter's second tier and for the conversation memory.
   On RHEL the role also installs `pgedge-postgresql<ver>-server`.

The packages enable and start none of the Workbench's services, and on RHEL
they do not start nginx either. `setup_ai_dba_workbench` writes their
configuration first, and then enables and starts each one.

!!! warning "The knowledge base package"
    The `pgedge-ai-dba-server` package published as 1.0.0-1 requires
    `pgedge-ai-kb`, a prebuilt knowledge base of PostgreSQL and pgEdge
    documentation. It is about 2.2 GB to download and about 2.6 GB once
    installed, so the Workbench host needs the disk for it. On Ubuntu 26.04
    the server package does not require it, and the pgEdge repository
    publishes no `pgedge-ai-kb` package for that release. The roles leave the
    Workbench's knowledge base search turned off.

## Artifacts

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/usr/bin/ai-dba-server` | New | The Workbench server, which serves the REST API and the MCP endpoint, and whose command-line options manage the Workbench's users. |
| `/usr/bin/ai-dba-collector` | New | The collector, which reads statistics from the monitored servers into the datastore, and creates and migrates the datastore's schema. |
| `/usr/bin/ai-dba-alerter` | New | The alerter, which evaluates alert rules and detects anomalies in what the collector records. |
| `/usr/share/pgedge/ai-dba-client/` | New | The web client's files, which nginx serves. |
| `/etc/pgedge/ai-dba-server.yaml`, `/etc/pgedge/ai-dba-collector.yaml`, `/etc/pgedge/ai-dba-alerter.yaml` | New | The packaged configuration files, which `setup_ai_dba_workbench` writes over. |
| `pgedge-ai-dba-server.service`, `pgedge-ai-dba-collector.service`, `pgedge-ai-dba-alerter.service` | New | The services' systemd units, which the packages leave disabled and stopped. |

## Platform-Specific Behavior

The Workbench's own packages have the same names on both families. The
Postgres packages differ, as `install_lakekeeper` documents for Lakekeeper's
catalog: on RHEL the base `pgedge-postgresql<ver>` package is client tools
only, and the server binaries live in `pgedge-postgresql<ver>-server`, which
this role also installs.

| Package | Debian | RHEL |
|---------|--------|------|
| Postgres server | `pgedge-postgresql-<ver>` | `pgedge-postgresql<ver>` and `pgedge-postgresql<ver>-server` |
| pgvector | `pgedge-postgresql-<ver>-pgvector` | `pgedge-pgvector_<ver>` |

The web client package installs its nginx site in a different place on each
family. On Debian it is `/etc/nginx/sites-available/pgedge-ai-dba-client`,
which the package links into `/etc/nginx/sites-enabled`; on RHEL it is
`/etc/nginx/conf.d/pgedge-ai-dba-client.conf`, which nginx reads without a
link. `setup_ai_dba_workbench` writes over the file in either place.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. Package
installation is a no-op once already done.
