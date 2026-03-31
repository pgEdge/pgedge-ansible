# Role Reference

This page describes each role in the pgEdge Ansible Collection, its purpose,
and the host groups it targets.

## Role Execution Order

Roles must be applied in a specific order to satisfy dependencies.
The following list shows the correct execution sequence:

1. [`init_server`](#the-init_server-role) - Prepares all servers in the
   cluster.
2. [`install_repos`](#the-install_repos-role) - Installs the pgEdge and PGDG
   package repositories.
3. [`install_pgedge`](#the-install_pgedge-role) - Installs pgEdge packages on
   pgEdge nodes.
4. [`setup_postgres`](#the-setup_postgres-role) - Initializes PostgreSQL on
   pgEdge nodes.
5. [`install_etcd`](#the-install_etcd-role) - Installs etcd on pgEdge nodes
   (HA only).
6. [`install_patroni`](#the-install_patroni-role) - Installs Patroni on pgEdge
   nodes (HA only).
7. [`install_backrest`](#the-install_backrest-role) - Installs PgBackRest on
   backup-capable nodes.
8. [`setup_etcd`](#the-setup_etcd-role) - Configures and starts etcd
   (HA only).
9. [`setup_patroni`](#the-setup_patroni-role) - Configures Patroni and starts
   the HA cluster (HA only).
10. [`setup_haproxy`](#the-setup_haproxy-role) - Configures HAProxy on haproxy
    nodes (HA only).
11. [`setup_pgedge`](#the-setup_pgedge-role) - Creates Spock nodes and
    establishes subscriptions.
12. [`setup_backrest`](#the-setup_backrest-role) - Configures PgBackRest and
    runs the first backup.

## The init_server Role

The `init_server` role prepares each server to operate as part of the cluster.
Apply this role to every host group before running any other roles.

The role performs the following actions:

- Validates configuration, confirming that required parameters are set and
  that the target distribution is Debian or RHEL.
- Installs base packages: acl, jq, nano, less, and rsync.
- Disables `RemoveIPC` in systemd-logind to prevent shared memory segments
  from being removed when a user session ends. Restart of logind only occurs
  if the setting was changed.
- Adds all cluster nodes to `/etc/hosts` on every node when
  `manage_host_file` is true.
- Configures SELinux settings on RHEL-based systems.
- Enables core file retention when `debug_pgedge` is true.
- On pgEdge nodes in SSH backup mode, generates an SSH key pair for the
  `postgres` OS user and retrieves the public key to the Ansible controller.
- On dedicated backup nodes in SSH backup mode, creates the `backup_repo_user`
  OS account that owns the PgBackRest repository.

## The install_repos Role

The `install_repos` role installs the pgEdge and PGDG package repositories
on each target node. Apply this role to pgEdge nodes and backup nodes
immediately after `init_server` and before any software installation role.

The role performs the following actions on Debian systems:

- Installs the pgEdge release package to configure the pgEdge apt repository.
- Installs the PGDG apt repository for the target PostgreSQL version.

The role performs the following actions on RHEL systems:

- Installs the pgEdge release RPM to configure the pgEdge dnf repository.
- Installs EPEL and the PGDG dnf repository for the target PostgreSQL version.

## The install_pgedge Role

The `install_pgedge` role installs pgEdge software packages. Apply this role
to all pgEdge nodes after `install_repos` has completed.

The role performs the following actions:

- Installs `pgedge-enterprise-all` and the psycopg2 package from the pgEdge
  repository using the system package manager.

## The setup_postgres Role

The `setup_postgres` role initializes the PostgreSQL instance and installs the
Spock and Snowflake extensions. Apply this role to all pgEdge nodes.

The role performs the following actions:

- Ensures the PostgreSQL data directory and configuration directory exist with
  the correct ownership.
- On RHEL, runs `postgresql-VERSION-setup initdb` to initialize the data
  directory.
- On Debian, uses `pg_createcluster` to create a named cluster.
- Creates all databases listed in `db_names` and installs Spock and Snowflake
  extensions on each database.
- Configures `pg_hba.conf` with least-privilege rules for known users and
  databases. Additional rules can be specified via `custom_hba_rules`.
- Generates a self-signed TLS certificate for PostgreSQL connections.
- In HA clusters, designates the first node in each zone as the Patroni
  primary and prepares all remaining nodes in the zone as streaming replicas.

## The install_etcd Role

The `install_etcd` role installs etcd from system packages. Apply this role
to all pgEdge nodes in an HA cluster. The etcd service is not started during
this role.

The role performs the following actions:

- Installs the etcd package from the pgEdge repository.
- Creates the etcd system user and data directory.
- Registers the etcd systemd service without starting it.

## The install_patroni Role

The `install_patroni` role installs Patroni from system packages. Apply this
role to all pgEdge nodes in an HA cluster. The Patroni service is not started
during this role.

The role performs the following actions:

- Installs OS-specific prerequisite packages for Debian or RHEL.
- Installs the Patroni package from the pgEdge repository.
- Creates the Patroni configuration directory at `/etc/patroni`.
- Registers the Patroni systemd service without starting it.

## The install_backrest Role

The `install_backrest` role installs PgBackRest from system packages. Apply
this role to pgEdge nodes and backup nodes where backup is required.

The role performs the following actions:

- Installs the PgBackRest package from the pgEdge repository.

## The setup_etcd Role

The `setup_etcd` role configures etcd and starts the service. Apply this role
to all pgEdge nodes in an HA cluster after `install_etcd` has completed.

The role performs the following actions:

- Generates TLS certificates for etcd peer and client communication.
- Generates the etcd configuration file from a template, listing all nodes in
  the same zone as cluster peers.
- Starts the etcd systemd service if the data directory does not already
  exist.

## The setup_patroni Role

The `setup_patroni` role configures Patroni and starts the HA cluster. Apply
this role to all pgEdge nodes in an HA cluster after `setup_etcd` has
completed.

The role performs the following actions:

- Generates TLS certificates for Patroni REST API communication.
- Generates the `patroni.yaml` configuration file from a template.
- Starts the Patroni systemd service.
- Waits for the cluster primary to become available before proceeding.
- Waits for the cluster to reach a running state (up to 30 retries with a
  10-second delay between attempts).

Patroni configures PostgreSQL with the following settings for Spock
compatibility:

- WAL level set to logical.
- Shared preload libraries set to pg_stat_statements, snowflake, and spock.
- DDL replication enabled via Spock.
- Spock replication slots excluded from Patroni slot management to prevent
  conflicts.

## The setup_haproxy Role

The `setup_haproxy` role installs and configures HAProxy on dedicated proxy
nodes. Apply this role to the haproxy host group before running
`setup_pgedge`.

The role performs the following actions:

- Installs HAProxy from the distribution package repository.
- Generates `haproxy.cfg` from a template, creating listeners for the primary
  connection port (5432 by default) and any additional routes defined in
  `haproxy_extra_routes`.
- Configures HTTP health checks against the Patroni REST API on port 8008 for
  each backend server.
- Restricts backend servers to nodes in the same zone as the HAProxy node.
- Enables the HAProxy statistics interface on port 7000.

## The setup_pgedge Role

The `setup_pgedge` role creates pgEdge Spock nodes and establishes replication
subscriptions between zones. Apply this role to all pgEdge nodes after
`setup_haproxy` has completed (in HA clusters).

The role performs the following actions:

- Creates a Spock node named `edge[ZONE]` with the appropriate connection
  string.
- Sets the Spock exception behavior to the value of `exception_behaviour`.
- Sets the Snowflake node ID to the zone number.
- Enables DDL replication via Spock.
- Subscribes to every other zone in the cluster.

In HA clusters, the role runs only on the first node in each zone.
Subscriptions target the HAProxy node in the remote zone when one is
available. The `proxy_port` parameter controls the port used for these
connections, allowing HAProxy to run on a pgEdge node rather than a dedicated
host. When `proxy_node` is set, that value is used instead of automatic
selection.

## The setup_backrest Role

The `setup_backrest` role configures PgBackRest and runs the initial backup.
Apply this role to pgEdge nodes and backup nodes after all other roles have
completed.

The role performs the following actions:

- Creates the `backup_user` PostgreSQL role with `pg_checkpoint` privileges
  and configures `pg_hba.conf` to allow backup connections.
- Generates `pgbackrest.conf` from a template, configuring the repository
  type, path, encryption, and retention settings.
- For SSH repositories, configures SSH access between the pgEdge node and the
  backup server using the `postgres` OS user.
- Configures PostgreSQL to archive WAL files to the PgBackRest repository and
  to retrieve WAL files from the repository during recovery.
- Initializes the backup repository stanza for each zone.
- Runs the first backup to bootstrap the repository.
- Creates cron entries for scheduled full and differential backups.
