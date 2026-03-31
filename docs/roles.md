# Role Reference

This page describes each role in the pgEdge Ansible Collection, its
purpose, and the host groups it targets.

## Role Execution Order

Roles must be applied in a specific order to satisfy dependencies.
The following list shows the correct execution sequence:

1. `init_server` - Prepares all servers in the cluster.
2. `install_pgedge` - Installs the pgEdge CLI on pgEdge nodes.
3. `setup_postgres` - Initializes PostgreSQL on pgEdge nodes.
4. `install_etcd` - Installs etcd on pgEdge nodes (HA only).
5. `install_patroni` - Installs Patroni on pgEdge nodes (HA only).
6. `install_backrest` - Installs PgBackRest on backup-capable nodes.
7. `setup_etcd` - Configures and starts etcd (HA only).
8. `setup_patroni` - Configures Patroni and starts the HA cluster
   (HA only).
9. `setup_haproxy` - Configures HAProxy on haproxy nodes (HA only).
10. `setup_pgedge` - Creates Spock nodes and establishes subscriptions.
11. `setup_backrest` - Configures PgBackRest and runs the first backup.

## init_server

The `init_server` role prepares each server to operate as part of the
cluster. Apply this role to every host group before running any other
roles.

The role performs the following actions:

- Installs base packages: jq, nano, less, and rsync.
- Creates a `.bashrc.d` directory for modular environment
  configuration.
- Adds all cluster nodes to `/etc/hosts` on every node when
  `manage_host_file` is true.
- Configures SELinux settings on RHEL-based systems.
- Enables core file retention when `debug_pgedge` is true.
- Retrieves the public SSH key from each node and stores the keys in
  a `host-keys` directory on the Ansible controller.

## install_pgedge

The `install_pgedge` role downloads and installs the pgEdge CLI.
Apply this role to all pgEdge nodes and any backup nodes that require
the CLI.

The role performs the following actions:

- Downloads the pgEdge installer from the configured repository.
- Runs the Python-based installation script.
- Adds the pgEdge CLI to the PATH environment for the Ansible user.

## setup_postgres

The `setup_postgres` role initializes PostgreSQL using the pgEdge CLI
and installs the Spock and Snowflake extensions. Apply this role to
all pgEdge nodes.

The role performs the following actions:

- Runs `pgedge setup` to initialize the PostgreSQL instance.
- Creates all databases listed in `db_names`.
- Installs Spock and Snowflake extensions on each database.
- In HA clusters, stops PostgreSQL and wipes the data directory on
  all nodes except the first node in each zone. Those nodes are
  prepared as streaming replicas for Patroni.

## install_etcd

The `install_etcd` role downloads and installs etcd. Apply this role
to all pgEdge nodes in an HA cluster. The etcd service is not started
during this role.

The role performs the following actions:

- Downloads etcd from the upstream release archive on GitHub.
- Installs the etcd binaries to `/usr/local/etcd`.
- Creates the etcd system user and data directory.
- Registers the etcd systemd service without starting it.

## install_patroni

The `install_patroni` role installs Patroni using pipx. Apply this
role to all pgEdge nodes in an HA cluster. The Patroni service is not
started during this role.

The role performs the following actions:

- Installs OS-specific prerequisite packages for Debian or RHEL.
- Installs Patroni via pipx to isolate Python dependencies.
- Creates the Patroni configuration directory at `/etc/patroni`.
- Registers the Patroni systemd service without starting it.

## install_backrest

The `install_backrest` role installs PgBackRest using the pgEdge CLI.
Apply this role to pgEdge nodes and backup nodes where backup is
required.

The role performs the following actions:

- Downloads and installs PgBackRest via the pgEdge CLI.
- Adds the PgBackRest binary directory to the PATH environment.

## setup_etcd

The `setup_etcd` role configures etcd and starts the service. Apply
this role to all pgEdge nodes in an HA cluster after
`install_etcd` has completed.

The role performs the following actions:

- Generates the etcd configuration file from a template, listing all
  nodes in the same zone as cluster peers.
- Starts the etcd systemd service if the data directory does not
  already exist.

## setup_patroni

The `setup_patroni` role configures Patroni and starts the HA cluster.
Apply this role to all pgEdge nodes in an HA cluster after
`setup_etcd` has completed.

The role performs the following actions:

- Generates the `patroni.yaml` configuration file from a template.
- Starts the Patroni systemd service.
- Waits for the cluster to reach a running state (up to 30 retries
  with a 10-second delay between attempts).
- Restarts PostgreSQL via patronictl to apply configuration changes.

Patroni configures PostgreSQL with the following settings for Spock
compatibility:

- WAL level set to logical.
- Shared preload libraries set to pg_stat_statements, snowflake,
  and spock.
- DDL replication enabled via Spock.
- Spock replication slots excluded from Patroni slot management to
  prevent conflicts.

## setup_haproxy

The `setup_haproxy` role installs and configures HAProxy on dedicated
proxy nodes. Apply this role to the haproxy host group before running
`setup_pgedge`.

The role performs the following actions:

- Installs HAProxy from the distribution package repository.
- Generates `haproxy.cfg` from a template, creating listeners for
  the primary connection port (5432 by default) and any additional
  routes defined in `haproxy_extra_routes`.
- Configures HTTP health checks against the Patroni REST API on port
  8008 for each backend server.
- Restricts backend servers to nodes in the same zone as the
  HAProxy node.
- Enables the HAProxy statistics interface on port 7000.

## setup_pgedge

The `setup_pgedge` role creates pgEdge Spock nodes and establishes
replication subscriptions between zones. Apply this role to all
pgEdge nodes after `setup_haproxy` has completed (in HA clusters).

The role performs the following actions:

- Creates a Spock node named `edge[ZONE]` with the appropriate
  connection string.
- Sets the Spock exception behavior to the value of
  `exception_behaviour`.
- Sets the Snowflake node ID to the zone number.
- Enables DDL replication via Spock.
- Subscribes to every other zone in the cluster.

In HA clusters, the role runs only on the first node in each zone.
Subscriptions target the HAProxy node in the remote zone when one is
available. When `proxy_node` is set, that value is used instead.

## setup_backrest

The `setup_backrest` role configures PgBackRest and runs the initial
backup. Apply this role to pgEdge nodes and backup nodes after all
other roles have completed.

The role performs the following actions:

- Generates `pgbackrest.conf` from a template, configuring the
  repository type, path, encryption, and retention settings.
- For SSH repositories, configures SSH access between the pgEdge
  node and the backup server.
- Configures PostgreSQL to archive WAL files to the PgBackRest
  repository and to retrieve WAL files from the repository during
  recovery.
- Initializes the backup repository stanza for each zone.
- Runs the first backup to bootstrap the repository.
- Creates cron entries for scheduled full and differential backups.
