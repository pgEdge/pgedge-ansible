# Unreleased

These notes describe the changes since v2.1.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

## Overview

This release adds the pgEdge AI DBA Workbench, a monitoring and AI-assisted
management tool, on a host of its own that monitors every node of the
cluster. Its main features are:

- New `install_ai_dba_workbench` and `setup_ai_dba_workbench` roles that build
  the Workbench host, and a new `setup_ai_dba_workbench_monitor` role that
  prepares the pgEdge nodes for it.
- New `simple-cluster-ai-dba-workbench` and `ultra-ha-ai-dba-workbench` sample
  playbooks and inventories. See
  [AI DBA Workbench Configuration](../configuration/ai_dba_workbench.md).

## Upgrading from v2.1.0

The AI DBA Workbench is optional, and nothing changes for a cluster that does
not have an `ai_dba_workbench` host. Playbooks and inventories written for
v2.1.0 need no changes.

## Changes

### Added

- New `install_ai_dba_workbench` and `setup_ai_dba_workbench` roles deploy the
  pgEdge AI DBA Workbench, a monitoring and AI-assisted management tool for
  Postgres, on the host in a new `ai_dba_workbench` inventory group. They
  install the Workbench's 1.0.0 packages from the pgEdge repository:
  `pgedge-ai-dba-server`, `pgedge-ai-dba-collector`, `pgedge-ai-dba-alerter`
  and `pgedge-ai-dba-client`. The Workbench's datastore is a Postgres instance
  of its own on that host, with pgvector, which the alerter's second tier and
  the conversation memory use. `setup_ai_dba_workbench` initializes it and
  runs it as its own `ai-dba-workbench-postgres` service, listening on
  `pg_port` at the loopback address only, as `setup_lakekeeper` runs the
  Lakekeeper catalog's. Each service's configuration names files that hold
  its secrets: the datastore password, and one secret, generated once and kept,
  that the server encrypts stored passwords with and the collector and alerter
  decrypt them with. The collector starts first, and the server only once the
  collector has built the datastore's schema, which the server refuses to start
  without; the alerter starts last. nginx serves the web client, and proxies
  the REST API and the MCP endpoint to the server, over HTTPS on
  `ai_dba_workbench_port`, 8444 by default, with the certificate the inventory
  names in `ai_dba_workbench_tls_cert_source` and
  `ai_dba_workbench_tls_key_source` or a self-signed one generated on the
  controller. The server listens on the loopback interface only. Each service,
  and nginx, is restarted when a file it reads is newer than its running
  process. See [AI DBA Workbench
  Configuration](../configuration/ai_dba_workbench.md). (EE-50)
- The Workbench runs on one host, and `init_server` refuses a second in the
  `ai_dba_workbench` group. The collector, alerter and web client packages each
  require the server package of the same version, the packaged nginx site
  proxies to a server on the same host, and the three services share one
  datastore and one secret, so a second host would be a second Workbench.
  Keeping the datastore off the monitored cluster keeps its writes off the
  nodes and out of Spock replication, and monitoring keeps working while the
  cluster is down. The server package published as 1.0.0-1 requires
  `pgedge-ai-kb`, a documentation knowledge base of about 2.6 GB, so the host
  needs the disk for it; on Ubuntu 26.04 it does not, and the pgEdge
  repository publishes no `pgedge-ai-kb` there. The roles do not configure the
  Workbench's knowledge base search. (EE-50)
- `setup_ai_dba_workbench` creates the Workbench administrator,
  `ai_dba_workbench_admin_user`, with the server's command-line tool, signs in
  to the REST API as that user, and registers every pgEdge node under its
  inventory name. Each node is registered at its own address and Postgres port,
  rather than through HAProxy or pgBouncer, with `sslmode` `require`, so the
  Workbench sees each member of an HA zone and works out the cluster's
  replication topology itself. A registered node whose record differs from the
  inventory is updated with the fields that differ. The Workbench never returns
  a stored password, so the role records a SHA-256 digest of the monitoring
  passwords it last gave the Workbench in `/etc/pgedge/ai-dba-monitor.sha256`,
  and gives every node its password again when the inventory's no longer match
  it, or when the run generated a new secret in place of a lost one. A sign-in
  the Workbench refuses, as it does after `ai_dba_workbench_admin_password`
  changes, has the role set the inventory's password with the command-line tool
  and sign in again. Nodes the inventory no longer lists stay registered, since
  the Workbench cannot tell the servers the role registered from those
  registered in its web client, and `wipe_cluster` does not touch the Workbench
  host. (EE-50)
- The new `setup_ai_dba_workbench_monitor` role prepares every node to be
  monitored. It installs the `system_stats` extension's package on every
  member, and creates `ai_dba_workbench_monitor_user` with `pg_monitor`, the
  `pg_stat_statements` and `system_stats` extensions in `postgres` and every
  database the collection creates, and grants the role `monitor_system_stats`,
  read access to `pg_hba_file_rules` and `pg_ident_file_mappings`, and read
  access to Spock's node, subscription, exception log and resolution tables.
  It runs on the `pgedge` group after `setup_pgedge`, so that each of those
  databases exists by then, ColdFront's included, and creates those objects on
  each zone's leader only, since each node asks its own Postgres whether it is
  a standby. Each session it opens turns Spock's DDL replication off: by then
  the databases are in Spock, and each node creates these objects itself. It
  stops where the inventory has no `ai_dba_workbench` host, since `init_server`
  checks the monitoring password only where there is one. (EE-50)
- New `pg_required_hba_rules` in `role_config` holds the client authentication
  rules the collection depends on beyond the cluster's own hosts, which
  `setup_postgres` writes into `pg_hba.conf` on a simple cluster and
  `setup_patroni` writes into Patroni's configuration on an HA one. Each rule
  names the hosts it admits, which its writer resolves to their addresses.
  Where the inventory has an `ai_dba_workbench` host, it holds
  `pg_ai_dba_workbench_hba_rules`, which admits that host as
  `ai_dba_workbench_monitor_user`, to every database. Neither role names the
  Workbench, and since the rule is among those each writes whenever it
  rewrites `pg_hba.conf`, a later run of either alone keeps it. (EE-50)
- New `ai_dba_workbench_*` parameters set the Workbench's passwords, ports and
  certificate. `ai_dba_workbench_llm_provider` (`anthropic`, `openai`, `gemini`
  or `ollama`) and `ai_dba_workbench_embedding_provider` (`openai`, `gemini`,
  `voyage` or `ollama`) turn on the Workbench's chat and conversation memory
  and the alerter's reasoning and similarity tiers. Left empty, as they are by
  default, the Workbench monitors and raises alerts from its statistical tier
  alone. A key file is written, and named in the configuration, only for a
  provider that is set, since the Workbench server refuses to start with a key
  file it cannot read. (EE-50)
- `init_server` refuses an `ai_dba_workbench` group of more than one host or
  one that shares a host with the `pgedge` group, a default or empty
  `ai_dba_workbench_monitor_password` on either group, a default or empty
  `ai_dba_workbench_db_password`, a default `ai_dba_workbench_admin_password`,
  an administrator password shorter than 12 characters or longer than 72
  bytes, colliding `pg_port`, `ai_dba_workbench_port` and
  `ai_dba_workbench_server_port` on the Workbench host, a certificate without
  its key, and model settings with an unknown provider, no model, or no key or
  address. The Workbench's own list of common passwords, which it also refuses,
  is not checked. (EE-50)
- New `simple-cluster-ai-dba-workbench` and `ultra-ha-ai-dba-workbench` sample
  playbooks and inventories deploy the two clusters with the Workbench. They
  are the plain playbooks with `setup_ai_dba_workbench_monitor` after
  `setup_pgedge`, and a play for the `ai_dba_workbench` group at the end. Both
  end-to-end tests take the Workbench as a layer, a Workbench host from
  `tests/compose/ai-dba-workbench-*.yml` and
  `tests/inventories/ai-dba-workbench.yml`.
  `tests/run-test.sh ... ai-dba-workbench` deploys from the new samples, and
  refuses `coldfront` beside it, since no sample deploys both. The workflows'
  `ai_dba_workbench` input adds the host to the test playbooks, which can carry
  ColdFront as well. The Ultra-HA workflow's recovery test does not run with
  it, since the recovery's inventory has no Workbench host.
  `tests/verify/verify-ai-dba-workbench.yml` then checks the monitoring role
  and extensions on every member, the services and the HTTPS web client on the
  Workbench host, that every node is registered and reached by the collector,
  that the monitoring role reads what the probes read, and that another host is
  refused both the monitoring role and the server's port.
  `tests/check-ai-dba-workbench-idempotence.sh` checks that re-applying the
  Workbench's roles changes nothing. The new offline
  `tests/render/check-ai-dba-workbench.py` renders the role's configuration
  files and derived records, and the rule that admits the Workbench host,
  across model settings and inventories, and `tests/render/check-validate.py`
  and `tests/render/check-patroni.py` check the new refusals and the Patroni
  rule. (EE-50)
