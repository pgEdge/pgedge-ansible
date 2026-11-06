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

Changes to `db_names` now reach a running cluster. A database added to the list
is created on every node and joins Spock the next time the deployment playbook
runs, including on an Ultra-HA cluster whose leaders Patroni has moved off each
zone's first node. Removing a database from the list no longer shrinks the
worker and slot pools the cluster may still need.

Running the deployment playbook again against a deployed cluster now changes
nothing and reports nothing changed, whether or not Patroni has since moved a
zone's leader, and the end-to-end tests hold every deployment to that.

## Upgrading from v2.1.0

Playbooks and inventories written for v2.1.0 need no changes, unless they set
`db_names` to different lists on different pgEdge nodes. `init_server` now
refuses that; set `db_names` once, on the `pgedge` group.

A run whose `--limit` leaves out the node running a zone's primary now stops
rather than skipping the writes to that zone. Include each zone's primary in
the limit.

The AI DBA Workbench is optional, and nothing changes for a cluster that does
not have an `ai_dba_workbench` host.

## Changes

### Added

- New `zone_primary` task file in `role_config` records, as the `zone_primary`
  fact, the node running each zone's primary: the zone's only node on a simple
  cluster, and the node Patroni reports as leader on an HA one. Only a zone
  never built takes its first node as the primary; a built zone whose Patroni
  is stopped everywhere has Patroni started on its members so they elect a
  leader, and stops the run if no member can start. Once Patroni runs, it
  stops the run unless Patroni reports exactly
  one leader among the zone's nodes and every node agrees which. It also stops
  the run when the primary is not among the play's hosts, as when `--limit`
  leaves it out. `setup_postgres` and `setup_pgedge` use it to
  choose where to write, and `finalize_backrest` uses it in place of the
  lookup it kept to itself. See
  [Zone Primary](../roles/role_config.md#zone-primary). (EE-44)
- New `sizing_floor` task file in `role_config` reads back the
  `max_worker_processes`, `max_replication_slots`, `max_wal_senders` and
  `max_active_replication_origins` each zone was last configured with, from
  `patroni.yml` on Ultra-HA and `postgresql.conf` otherwise, into the
  `pg_sizing_floor` fact that the calculated sizes never go below. It reads
  files rather than the running server, so it works whether or not Postgres
  is up. See [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)
- New `unmanaged_db_names` parameter lists databases that run on the cluster
  but that the collection does not manage: one removed from `db_names` and
  kept replicating, or one created by hand. The worker and slot formulas count
  each as a database that replicates, but the collection does nothing else
  with them. Without it, the sizing floor kept a removed database's share of
  the pools only until another database was added to `db_names`, which the
  formula then counted in its place, leaving too few workers and slots for
  both. `init_server` refuses a name listed in `unmanaged_db_names` and
  `db_names` both, or `coldfront_db` where ColdFront is enabled, which the
  sizing already counts. See
  [unmanaged_db_names](../configuration/cluster.md#unmanaged_db_names).
  (EE-44)

- `init_server` refuses an inventory whose pgEdge nodes do not all list the
  same databases in `db_names`, and likewise in `unmanaged_db_names`. Spock
  subscribes each database in `db_names` to the same database on every other
  node, so a node with a different list either subscribes to databases its
  peers never create or leaves out ones they replicate, and every node's
  worker and slot pools are sized for every database. The order of the names
  does not matter, and a node that leaves `db_names` unset counts as having
  its default. The refusal names each differing list and the nodes that hold
  it. (EE-44)
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

### Fixed

- `max_worker_processes` counts the Spock manager worker in `coldfront_db`
  where ColdFront is enabled outside mesh mode. Spock starts one in every
  database that accepts connections, but the formula counted only the
  databases in `db_names`, which outside mesh mode do not include
  `coldfront_db`, leaving one worker fewer than the cluster needs. (EE-44)

- A database added to `db_names` now reaches a running cluster when the
  deployment playbook runs again. Each node gets the database and the Spock and
  Snowflake extensions, client authentication rules that name it, and Spock
  subscriptions to every other zone's copy of it. Previously, an Ultra-HA
  cluster whose leaders Patroni had moved off each zone's first node failed
  outright: `setup_postgres` tried to create the database on a read-only
  replica, and `setup_patroni` waited for the first node to report itself
  running, which a Patroni replica never does. Even with the leaders in place,
  `setup_patroni` rewrote `patroni.yml` without reloading Patroni, so the new
  database stayed closed to subscriptions arriving through the other zones'
  proxies. A simple cluster had the same gap whenever the new database left
  the worker and slot sizing unchanged, because `setup_postgres` reloaded
  Postgres only for a changed `postgresql.conf`. (EE-44)
- Removing a database from `db_names` no longer shrinks the calculated
  `max_worker_processes`, `max_replication_slots`, `max_wal_senders` and
  `max_active_replication_origins` beneath what the running cluster still uses.
  The collection never drops a database, its Spock node or its subscriptions,
  so sizing from `db_names` alone left the pools too small after the next
  restart: Spock could not start the workers it needed, and Postgres refused to
  start when it held more slots than `max_replication_slots` allowed. Each run
  now sizes the pools no smaller than each zone was last configured with, so
  the calculated sizes only ever go up. Setting them in `pg_parameters` still
  replaces the calculation, which is how to lower them. See
  [Sizing Floor](../roles/role_config.md#sizing-floor). (EE-44)
- The configuration reference now says what removing a name from `db_names`
  means: the collection stops managing the database but does not drop it. It
  lists what the database no longer gets, including its `pg_hba` rules, which
  stops its replication the next time a subscription reconnects. Because
  `spock.sub_drop` cannot then reach the provider to drop the subscription's
  slot, it gives the order in which to retire a database before removing its
  name, and how `custom_hba_rules` reopens access to one already removed. See
  [Removing a database from
  db_names](../configuration/cluster.md#removing-a-database-from-db_names).
  (EE-44)
- `setup_patroni` reloads Patroni on a node where it was already running and
  `patroni.yml` changed, and waits for the zone's leader, wherever it is,
  rather than for the first node. (EE-44)
- `setup_postgres` no longer edits `pg_hba.conf` or `postgresql.conf` on a node
  Patroni already manages. It used to rewrite Patroni's `pg_hba.conf` on every
  run with rules missing the proxies' access to the databases in `db_names`,
  which took effect the next time anything reloaded Postgres. (EE-44)
- The end-to-end tests run `tests/playbooks/db-add.yml` against both
  scenarios, except with ColdFront. On Ultra-HA it first moves each zone's
  leader to the zone's second node. It then adds a database, checks that it
  exists on every node and that a row written in one zone reaches every other.
  It takes the name back out of `db_names` while the database still replicates
  and checks that every node keeps the pools the database needs, then drops it,
  checks that the pools return to what the deployment needs, and puts the
  leaders back. (EE-44)
- Running the deployment playbook a second time against a deployed cluster
  reports no changes. Previously every run reported several on each pgEdge
  node, which hid any real change among them:
  - Spock's node and subscription tasks reported a change whether or not they
    created anything. They now report one only when they do.
  - The wait for a zone's Patroni leader reported a change every time.
  - `setup_postgres` rebuilds `pg_hba.conf` on every run of a node Patroni
    does not manage, and every rule it wrote reported a change. Only a file
    that ends up different now does, which is also what decides the reload.
  - On Debian, `setup_postgres` set the configuration directory in
    `/etc/postgresql` to mode `0700`, and `pg_createcluster` set it back to
    Debian's `0755` when it created the cluster, and again whenever Patroni
    cloned a replica. Each run then reported closing it. `setup_postgres` now
    leaves the directory's mode to `pg_createcluster`, and the files in it keep
    their own. On RHEL the configuration directory is the data directory,
    which stays `0700`.
  - In SSH mode, the backup servers' and pgEdge nodes' `known_hosts` entries
    for each other were taken from `ssh-keyscan`, run on the controller, and
    handed over in whatever order its keys arrived, which changes from one
    scan to the next. Each run could replace an entry, and a scan refused while
    every fork scanned the same host failed the run. Each host's ed25519 key
    now comes from the facts the deployment gathers; only a `backup_host`
    outside the inventory is still scanned, for that one key.
  - Refreshing the APT cache no longer reports a change.
  (EE-49)
- A changed `pgedge_password`, `replication_password` or `backup_password`
  now reaches the `.pgpass` file that uses it. The entry was only ever
  appended, and libpq takes the first entry that matches, so the old password
  kept being used: Spock's subscriptions failed to authenticate the next time
  they reconnected. Each entry is now written by a new `pgpass_entry` task
  file in `role_config`, which first removes any entry for the role with a
  different password, including duplicates earlier runs left behind, and
  escapes colons and backslashes as `.pgpass` requires. A password containing
  either was previously written in a form libpq could not match. (EE-49)
- On a simple cluster with a backup repository, the backup server's
  `pg_hba.conf` rules were added by `finalize_backrest` after `setup_postgres`
  had rebuilt the file without them. Each later run removed them, reloaded
  Postgres, added them back and reloaded again, refusing the backup server in
  between. `setup_postgres` now writes them with the rest, and
  `finalize_backrest` no longer edits `pg_hba.conf`. (EE-49)
- Every HA node now has the replication user's `.pgpass` entry, rather than
  only the zone's primary. Written only there, it was added to each node the
  first time a failover made that node the leader. (EE-49)
- Several steps that took a zone's first node for its primary now use
  `zone_primary`, so a run after a failover or switchover behaves as one before
  it (EE-49):
  - The backup server reads the cluster's timeline from the zone's primary.
    A replica's checkpoint moves to a new timeline only at its next
    restartpoint, so after a failover the first node could still report the
    old one, and a backup already taken on the new timeline looked
    unrestorable. The run then took a full backup, which with
    `full_backup_count` at 1 expired the previous one.
  - The check that a repository does not already hold the cluster runs on the
    zone's primary. Run on the first node, it refused a first node that had
    become a replica and been wiped for Patroni to clone again, which is the
    empty data directory beside a full repository that a replica has by
    design.
  - `finalize_backrest` checks the repository's identity and points Patroni
    at the repository from the zone's primary.
- `setup_patroni` forces a restart of a first node it starts only when that
  start bootstraps the zone. A first node rejoining a built zone as a replica,
  as after a failover, is restarted only when it has a restart pending and
  `pg_allow_restart` allows it. (EE-49)
- `recover_postgres` can restore a cluster whose worker or connection pools
  grew after the backup it restores, as they do when a database is added to
  `db_names`. Postgres refuses to replay WAL written by a server whose
  `max_worker_processes`, `max_wal_senders`, `max_connections`,
  `max_prepared_transactions` or `max_locks_per_transaction` was larger than
  its own. The restored node replayed with the pools in its configuration
  file: on RHEL the backup's own, which recovery paused on at the first larger
  record, and on Debian Postgres's defaults, which aborted at once. The
  restored node now replays with `hot_standby` off, where Postgres makes no
  such check, and starts with the pool sizes a deployment would give its
  zone. (EE-49)
- `tests/check-idempotence.sh` runs the whole deployment playbook a second
  time, rather than only the pooler roles, and fails if any task reports a
  change. The end-to-end tests also run it on Ultra-HA after moving each
  zone's leader to the zone's second node with the new
  `tests/playbooks/move-leaders.yml`, which then moves them back. (EE-49)
