# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

This release adds recovery of an existing cluster from its pgBackRest
repository, and reworks when the collection takes a backup so that redeploying a
cluster can never discard the recovery point its repository was holding.

### Added

- New `recover_cluster` role and `sample-playbooks/recover-cluster/` playbook
  rebuild an existing HA cluster from a pgBackRest repository, optionally to a
  point in time. One zone is restored from its repository and every other zone
  is rebuilt empty and refilled across Spock from the restored one, because each
  zone's stanza describes an independent physical cluster restored to an
  independent moment, and zones restored separately have no common position to
  replicate forward from. See
  [Recovering a Cluster from Backup](recovery.md).
- New `recovery_node`, `recovery_target_type`, `recovery_target`,
  `recovery_backup_set` and `recovery_confirm` parameters drive a recovery.
  All are empty or false by default, so an ordinary deployment renders exactly
  the configuration it did before.
- `setup_patroni` now renders a pgBackRest bootstrap method for the node
  `recovery_node` names, so Patroni restores that node from the repository
  rather than initializing an empty one. Patroni consults the `bootstrap`
  section only when it is genuinely bootstrapping a cluster, so the addition is
  inert on a running cluster.
- New `patroni_replica_from_backup` parameter makes Patroni rebuild a replica
  with a pgBackRest delta restore instead of a fresh `pg_basebackup` from its
  zone's leader, falling back to `pg_basebackup` if the restore fails. Off by
  default.
- New `finalize_backrest` role initializes the backup repository and the backup
  schedule: the backup database user, the stanza, the first backup and the cron
  entries. It is applied at the end of a deployment, where a running cluster
  exists for it to act on.
- `role_config` gained a `repo_identity` task file that compares a node's
  cluster against the one its stanza describes, and refuses when they disagree.
  `setup_postgres` asks it before initializing a data directory and
  `finalize_backrest` asks it before writing to the repository. The early check
  turns the disaster-recovery case — replacement hardware, the original
  inventory, and a repository that outlived the cluster — into a stop with an
  explanation rather than an empty cluster that can never archive to its own
  repository. It skips a repository it cannot reach, since an SSH repository is
  not reachable from a pgEdge node that early; the late check, which gates a
  decision to write, treats an unreadable repository as fatal.
- The recovery playbook now runs `pgbackrest stanza-upgrade` on every rebuilt
  zone. Those zones come back with a system identifier their stanza has never
  seen, so PgBackRest would refuse to archive there and the zone would finish
  the recovery unable to back itself up. The upgrade records the new cluster as
  another entry in the stanza's history and leaves the earlier backups in
  place, where retention expires them as new full backups accumulate.
- The Ultra-HA end-to-end test now verifies the backup surface rather than
  printing it. It asserts that the running server's `archive_command` invokes
  pgBackRest rather than the template's `/bin/true` placeholder, that WAL
  archiving is currently succeeding according to `pg_stat_archiver`, and that
  the repository holds exactly one healthy stanza with exactly one full backup.
  It then re-applies `finalize_backrest` and asserts the repository holds the
  same backups afterwards, which is the assertion that would have caught the
  destructive behaviour this release removes: a second full backup expires its
  predecessor under the default retention, so a repository rewritten that way
  still holds one backup and only its label changes.
- The recovery waits for the restore by watching whether it is still making
  progress rather than by counting attempts. How long a restore takes is a
  property of the database -- a full backup read out of the repository plus
  every WAL segment since -- so any fixed budget is wrong for some cluster. The
  waiter follows PgBackRest's restore log, `pg_control`'s timestamp and the size
  of the data directory, and gives up only when none has moved for
  `recovery_stall_minutes` (default 15). A restore that keeps moving is left
  alone however long it takes, and one that has wedged is reported in minutes
  rather than after a timeout drains. It runs under `async`, so a restore that
  outlasts an SSH connection is not lost with it.
- New `etcd_ca_cert` and `etcd_ca_key` supply the certificate authority that
  signs etcd's certificates and every node's Patroni client certificate, so it
  can live in Ansible Vault beside the passwords rather than only in a
  gitignored directory beside the playbook. That directory holds the one
  artifact nothing can recreate: `setup_etcd` generates the authority and then
  skips itself forever once the etcd data directory exists, while
  `setup_patroni` only signs against it — so a controller that lost it could no
  longer add a replica, rebuild a node, recover the cluster, or re-run the
  deployment. Both parameters are empty by default and an inventory that sets
  neither behaves exactly as before. A supplied authority that differs from the
  one already staged is refused rather than applied, because signing against a
  different authority than the running etcd trusts leaves no node able to reach
  the store.
- New `recovery_reset_dcs` rebuilds the distributed configuration store from
  nothing rather than removing the cluster from it, for when the store itself is
  what is broken -- etcd that has lost quorum, or keys a half-finished recovery
  left behind. It reissues each node's Patroni client certificate so the store
  and the nodes agree on a certificate authority. Applies only to the etcd
  cluster the collection deploys; an external store is reset by whoever runs it.
- New `tests/render/check-patroni.py` renders the Patroni template offline
  across every combination of the recovery switches, and asserts that a
  template rendered without facts for the proxy and backup hosts fails rather
  than emitting HBA rules with no addresses in them. The recovery playbook
  re-renders that template on the restored node partway through, after the
  cluster has been erased, so a template that cannot render there is expensive
  to discover live. Run by both workflows and both local harnesses.
- New `tests/run-recovery-test.sh`, `tests/playbooks/seed-recovery.yml` and
  `tests/verify/verify-recovery.yml` exercise a recovery against a cluster the
  end-to-end harness has already deployed. The seed writes rows *after* the
  deployment's backup, so they exist only in archived WAL: a recovery has to
  replay the archive to return them to the restored zone and carry them across
  Spock to the zones rebuilt empty. Every other check passes on an empty
  cluster, so this is what separates a restore from a rebuild. The verification
  also asserts the replication mesh was rebuilt to exactly the expected size --
  too many node entries or origins means metadata from before the recovery
  survived -- that every replica came back, and that each zone can archive
  again, which is what proves `stanza-upgrade` took on the rebuilt zones.
- New `backup_stanza` and `backup_repo_configured` variables in `role_config`,
  and `subscribe_target` moved there from `setup_pgedge`, so that the roles
  which now share them cannot drift apart.

### Changed

- The initial backup is now taken only when the repository reports that the
  stanza holds none, rather than on every run. `full_backup_count` defaults to
  `1`, so a full backup taken against a repository that already had one expired
  the previous full backup and its WAL the moment it completed — discarding the
  recovery point a redeployed cluster was about to be restored from. The
  decision is now made from the repository's contents rather than from where the
  role sits in a playbook.
- `setup_backrest` now writes files only and touches Postgres not at all, and
  moves before `setup_postgres` in the role order. An HA cluster gets its
  `archive_command` from the Patroni configuration, so Postgres starts archiving
  the moment Patroni starts it, and a `pgbackrest.conf` written later left a
  window in which every archive attempt failed. Placing it before
  `setup_postgres` also lets that role ask the repository whether it already
  holds a cluster before initializing a data directory. A non-HA cluster's
  `archive_command` and `restore_command` moved to `finalize_backrest`, which runs
  when Postgres is up to be reloaded.
- `recover_cluster`'s quiesce step now acts only on systemd units that exist, so
  a recovery can be run against replacement hardware where the deployment
  stopped before creating them. On RHEL the Postgres unit file is written by
  `setup_postgres`, and asking systemd to stop a unit it does not have is an
  error rather than a no-op.
- `archive_command` and `restore_command` for an HA cluster now come from
  `setup_patroni`'s configuration template rather than being patched into the
  Patroni configuration store by `setup_backrest`. A value held only in the
  store is lost when the cluster is removed from the store and bootstrapped
  again, which is what a recovery does: a recovered cluster came back with
  `archive_command` reverted to `/bin/true` and silently stopped archiving.
  `setup_backrest`'s `config_postgres_ha.yaml` has been removed.
- The Patroni template now spells replica creation as `create_replica_methods`
  rather than the legacy `create_replica_method`. Patroni accepts both.

### Security

- `backup_repo_cipher` no longer defaults to a value derived from `cluster_name`
  and `zone`. Both are public, so the password protecting every backup was
  reproducible by anyone who knew the cluster's name — encryption in form only.
  It cannot be defaulted at all: a generated password must be identical on every
  run, or the repository stops being readable, and must also be unguessable, and
  nothing can be both. `init_server` now requires one, the way it already
  requires the other passwords, and the parameter moved to `role_config` so that
  validation and the configuration template read the same value.

  Existing clusters keep working and must set the parameter explicitly. Their
  repositories are encrypted with the old derived password, and the derivation
  was public, so it can be recovered — `docs/configuration/backup.md` gives the
  command. Treat a recovered value as compromised and plan to re-encrypt.

### Fixed

- `backup_repo_cipher_type: none` now produces a configuration PgBackRest
  accepts. The repository template emitted `repo1-cipher-pass` unconditionally,
  and PgBackRest rejects a password alongside a cipher type of `none`, so
  leaving encryption to the storage layer was not expressible — which is the
  arrangement that permits key rotation, since PgBackRest cannot rotate its own
  cipher. The password line is now emitted only where something is encrypting,
  and `init_server` rejects a password set where nothing is.
- `recover_cluster` no longer treats a configuration store it cannot read as a
  store with no cluster in it. The check that runs before any data directory is
  erased folded a failed `patronictl` into an empty member list, so an etcd that
  had stopped answering would pass it -- and the recovery would erase the whole
  cluster and then leave Patroni waiting forever for a leader whose key was
  still sitting there. An unreadable store now stops the recovery with nothing
  erased, and names `recovery_reset_dcs` as the way past it.
- `backup_repo_user` and `backup_repo_path` no longer derive from
  `ansible_user_id`. That is a fact, and a fact records which account the setup
  module ran as, so a play that gathers facts with `become` records `root` --
  and because fact gathering is smart by default, one such play poisons the
  value for every later play in the same run. The repository owner became
  `root` and its path `/home/root`. PgBackRest refuses to run as root, which is
  the only reason this surfaced at all rather than quietly building a
  repository somewhere nobody would look for it. Both now derive from a new
  `connection_user` in `role_config`, which prefers the `ansible_user`
  connection variable and falls back to the fact only where no login user is
  configured. `init_server` compares against the same value.
- `setup_backrest` no longer skips its client configuration entirely when
  `backup_repo_type` is `s3`. The role gated client setup on a backup server
  being named, and an S3 repository names none, so S3 clusters were left with no
  `pgbackrest.conf`, no archive command and no backups, with nothing reporting
  it. The gate is now whether a repository is configured at all.

## v1.1.0

This release adds optional pgBouncer connection pooling and support for an
externally managed Patroni configuration store. Both are opt-in: an inventory
that sets neither renders exactly the configuration v1.0.0 did, so existing
clusters upgrade in place.

### Added

- New `patroni_dcs` parameter selects the distributed configuration store
  Patroni uses and passes arbitrary connection settings to it, allowing an
  externally managed store such as Consul or ZooKeeper. Accepted types are
  `etcd3`, `etcd`, `consul`, `zookeeper`, and `exhibitor`. Patroni's
  `kubernetes` type is not accepted, because it discovers the API server from
  a pod environment or a kubeconfig rather than from a configured endpoint,
  and this collection installs Patroni on ordinary hosts. (EE-33)
- `install_patroni` now installs the Patroni client library that matches the
  configured `patroni_dcs` type. (EE-33)
- Ultra-HA end-to-end test now covers an externally managed Consul store in
  addition to the default etcd cluster. (EE-33)
- New `patroni_namespace` parameter sets the key prefix Patroni uses within
  the distributed configuration store, so a store shared by more than one zone
  can give each zone its own prefix. Defaults to `/db/`, which matches the
  previous hardcoded value. (EE-33)
- New `patroni_scope` parameter sets the cluster name Patroni uses within the
  distributed configuration store, so a store shared by more than one zone can
  give each zone its own scope instead of its own namespace prefix, which some
  stores make load-bearing. Defaults to `<pg_version>-<cluster_name>`, which
  matches the previous hardcoded value, and the `patronictl` invocations in
  `setup_patroni` and `setup_backrest` now name the cluster with it. (EE-33)
- `init_server` now asserts that `patroni_dcs.parameters` is present when
  `patroni_dcs.type` names a store the collection does not deploy, so a
  missing key fails before bootstrapping rather than while Patroni is
  configured. (EE-33)
- `role_config` gained a `pg_feature_checks` task file that asks the installed
  PostgreSQL binary which configuration parameters it recognizes.
  `setup_postgres` and `setup_patroni` include it so configuration can be
  gated on parameters that only some releases carry. (EE-34)
- New `install_pgbouncer` and `setup_pgbouncer` roles deploy a pgBouncer
  connection pooler on pgEdge nodes, giving each node a second endpoint on
  `pgbouncer_port` beside PostgreSQL's own. Pooling is opt-in through the new
  `pgbouncer_enabled` parameter, which is cluster-wide the way `is_ha_cluster`
  is: set it on the `pgedge` group and every node pools, leave it unset and
  the cluster renders exactly the configuration it did before. `init_server`
  rejects an inventory whose pgEdge nodes disagree, because a zone that pooled
  only some of its nodes would lose its pooled endpoint on the first failover
  to one of the others.
- Pooled connections authenticate through pgBouncer's `auth_query` rather than
  a maintained password list. `setup_postgres` creates a powerless
  `pgbouncer_auth` role and a `SECURITY DEFINER` lookup wherever the cluster
  pools, so every PostgreSQL role works through the pooled endpoint, including
  roles created after deployment, and a rotated password takes effect
  immediately. The lookup filters on the role's `VALID UNTIL`, so an expired
  password is refused at the pooler instead of being accepted there and failing
  the backend login. Only `pgbouncer_auth_password` is written to disk, and
  `init_server` refuses to deploy a pooled cluster while it is still the
  default.
- The pooler enforces its own client authentication rules, rendered into
  `/etc/pgbouncer/pg_hba.conf` from the same variables that drive the
  PostgreSQL rules. `custom_hba_rules` admits a client to both endpoints; the
  new `pgbouncer_hba_rules` admits it to the pooled endpoint alone.
  `init_server` validates both against the `pg_hba` subset pgBouncer can
  parse, since it skips a line it cannot parse rather than refusing to start.
  `pgbouncer_auth` reaches the pooler over its unix socket only: the rendered
  rules reject it on every address, ahead of the loopback and proxy rules that
  name every role, so the one account that can read stored verifiers is not
  also a network login.
- The pooled endpoint serves TLS from the same certificate PostgreSQL
  presents, staged from the controller rather than read out of `PGDATA` so an
  HA replica does not race Patroni's clone.
  `pgbouncer_client_tls_sslmode` defaults to `allow`, which accepts exactly
  what the direct endpoint accepts today.
- New `pooler_port` parameter fronts the poolers from the proxy layer, the way
  `proxy_port` fronts `pg_port`. Where the cluster pools, `setup_haproxy`
  emits a `pg-pooler` listener on it carrying every node of the zone — the
  same servers as the direct listener, differing only in the port —
  health-checked against Patroni's REST API like the direct listeners, and
  sizes the global connection ceiling to cover it. The existing listeners are
  unchanged, so Spock replication never routes through a pooler. `init_server`
  asserts the ports a host actually binds do not collide: the two proxy-layer
  ports against each other on any HAProxy node, and against `pg_port` and
  `pgbouncer_port` only where HAProxy shares a host with a pgEdge node, since
  that is the only topology where all four bind the same address.
- New documentation for pooling: role pages for both new roles, a Pooling
  Configuration reference, a pgBouncer troubleshooting page, the pooled
  listener and the port model in Proxy Configuration, `pgbouncer_enabled` in
  Inventory Structure, and an opt-in walkthrough in both tutorials.

### Fixed

- Spock replication no longer breaks on PostgreSQL releases carrying the fix
  for CVE-2026-6471, which refuse to load an output plugin that
  `output_plugin_libraries` does not name. Both simple and Ultra-HA clusters
  now set the parameter, and only on releases that recognize it, since earlier
  releases refuse to start when it appears. (EE-34)
- `init_server` now rejects an inventory that gives `proxy_port` the same value
  as `pg_port` on a host that runs HAProxy alongside a pgEdge node, a topology
  the proxy documentation supports. HAProxy could not bind its listener there,
  which surfaced as a service failure well after the playbook had configured
  the node rather than as a validation error before it started.
- `init_server` validations that read a host's own variables now run on the
  hosts that carry them rather than `run_once`. Ansible runs a `run_once` task
  on the first host of the play and evaluates its condition only there, so on an
  inventory that ordered a proxy, backup or client host first, these checks read
  variables that host did not have — reporting a failure against the wrong host,
  or skipping silently and reporting nothing at all. Affected the default
  password check, `pgbouncer_auth_password`, the pooler's TLS mode and HBA rule
  checks, the per-zone node check, the supported-OS check and both DCS checks.
  The two assertions that read the inventory as a whole, and so resolve the same
  from any host, still run once.
- `patroni_config_file` and `patroni_tls_dir` are now recognized by all roles.
- HA failover example in the usage guide now passes the Patroni scope the
  collection actually configures, which has included the PostgreSQL version
  since v1.0.0.
- Patroni replication user now connects to all databases for logical slot
  creation.
- `backup_repo_cipher` default is now properly deterministic.
- PostgreSQL contrib package is now installed explicitly on RHEL systems where
  it may be missing.

## v1.0.0

This release is a major overhaul that revises every role in the collection.
It replaces the pgEdge CLI component with standard RPM and DEB packages from
the pgEdge and PGDG package repositories. All local-user installation
semantics are removed in favor of the standard `postgres` OS user and
system-conventional paths.

**This is a breaking change.** Clusters deployed with v0.1 or v0.2 cannot be
upgraded in place. Re-provision all nodes from scratch before deploying to
production.

### Added

- New `install_repos` role installs the pgEdge and PGDG package repositories
  on each node before any software installation takes place. Add this role to
  all playbooks immediately after `init_server`. (EE-22)
- `custom_hba_rules` parameter accepts a list of custom `pg_hba.conf` rules
  to append to the default rule set.
- `backup_user` and `backup_password` parameters define a dedicated
  PostgreSQL user with `pg_checkpoint` privileges for backup operations.
- `backup_repo_user` parameter specifies the OS user that owns the PgBackRest
  repository in SSH backup mode.
- `proxy_port` parameter allows HAProxy to run on a pgEdge node by setting a
  proxy port separate from the PostgreSQL listen port.
- `pgedge_user` and `pgedge_password` parameters define the internal user
  used for node-to-node Spock connections.
- `tls_validity_days` parameter controls the validity period for generated
  TLS certificates.

### Fixed

- Patroni cluster initialization now waits for the primary to become
  available before performing administrative operations.

### Changed

- Switched to pgEdge distro-specific package repositories; `repo_name`
  default changed from `download` to `release`. (EE-22)
- PostgreSQL, etcd, Patroni, and PgBackRest are now installed from system
  packages rather than downloaded locally. The `install_base` and
  `cluster_path` parameters are removed.
- PostgreSQL now runs as the system `postgres` user. Data and configuration
  directories follow OS conventions: `/var/lib/postgresql/VERSION/main` and
  `/etc/postgresql/VERSION/CLUSTER` on Debian; `/var/lib/pgsql/VERSION/data`
  on RHEL.
- `pg_home`, `pg_path`, `pg_data`, and `pg_config_dir` are now computed
  from `pg_version` and OS family. The `cluster_path`-based path variables
  are removed.
- Default `pg_hba.conf` rules now use a least-privilege model and only
  include entries for known user and database combinations. Custom rules can
  be added via `custom_hba_rules`.
- `init_server` now disables `RemoveIPC` in systemd-logind, creates the
  `postgres` OS user on nodes that require SSH backup access, and validates
  configuration before any other tasks run.
- Updated default etcd version to 3.6.5.
- Spock extension is now always installed at the latest available version.
- Several parameters previously scattered across role defaults are now
  centralized in the `role_config` role.

## v0.2.0

### Added

- Ability to specify additional HAProxy listeners for specific Patroni node types. (EE-9)
- Restart Postgres in setup_patroni role to activate config changes. (EE-13)

### Changed

- Switched to upstream etcd and Patroni releases. (EE-15)
- Set default Spock version to 5.0.
- Set default Postgres version to 17.

## v0.1.0

The "real" release.

### Added

- Ability to specify multiple database names for subscription management. (EE-12)
- Ability to specify exception_behaviour as parameter. (EE-7)
- Can now specify proxy_node to override automatic haproxy zone target. (EE-3)

### Fixed

- Additional retries to circumvent Debian package management locks. (#15)
- replication_user and replication_password actually work now. (EE-14)
- Strip comments from ssh_keyscan output to avoid syntax errors. (#13)
- DDL replication now activates spock.allow_ddl_from_functions. (EE-10)
- Added lock_timeout parameter to all package tasks to avoid failures. (EE-8)
- Added explicit dependency to ansible.utils.ipaddr filter. (EE-1)

### Changed

- Renamed db_name role parameter to db_names to list multiple database names. (EE-12)

## v0.0.2

### Added

- Initial creation and setup roles for pgEdge cluster resources.
