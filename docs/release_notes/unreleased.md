# Unreleased

These notes describe the changes since v2.2.0 that have not yet been released.
The [Changelog](../CHANGELOG.md) summarizes them.

<!--
This page and the Unreleased section of the Changelog always exist. Each change
adds its entries under the headings below, and leaves the headings in place.
The release that ships them renames this file to vX.Y.Z.md, fills in the
Overview, and creates a fresh copy of this page in the same pull request.
-->

## Overview

## Upgrading from v2.2.0

## Changes

### Added

- The new [`update_software`](../roles/update_software.md) role applies minor
  updates to a deployed cluster's software. Each sample playbook runs it as
  its last play, where it does nothing until a run asks for it with
  `-e permit_software_updates=true`. It then updates every package the
  collection installed to the newest version the repositories offer, and
  etcd to `etcd_version`, restarting what needs it, one host at a time:

    - The pgEdge nodes go zone by zone. A zone's replicas go first, then its
      leader, after a switchover to an updated replica, so no zone's primary
      restarts in place. Each node's Patroni, Postgres and etcd are stopped
      before its packages change and started afterwards, and the next node
      waits until it streams from its leader again.
    - The Spock and Snowflake extensions are updated on each zone's primary
      where their packages ship a newer version.
    - The HAProxy hosts follow, one at a time.
    - pgBackRest is updated last, on every pgEdge node and backup server at
      once, because a client and repository host on different versions
      refuse each other. A running backup stops it.

  The run reports what it will update, and in what order, before it stops
  anything. It refuses to start when `pg_allow_restart` is `false`, and a run
  that stops partway resumes where it stopped. A run with nothing to update
  changes nothing. (#76)

### Changed

- `etcd_version` and `etcd_install_dir` are defaults of `role_config` rather
  than of `install_etcd` and `setup_etcd`, so `update_software` can compare a
  node's etcd with the release the collection installs. Their defaults and
  meaning are unchanged. (#76)

- `init_server` refuses a `cluster_name` that contains a hyphen on
  Debian-based systems. Debian runs each cluster as the
  `postgresql@<version>-<cluster>` service, and that unit reads every hyphen
  in the instance name as a path separator, so it looks for a cluster named
  `my-demo` in `/etc/postgresql/17/my/demo` and refuses to start it. Such a
  deployment used to stop partway through `setup_postgres` with only
  "Assertion failed" from systemd; it now stops before anything is installed,
  with a message that names the cause. RedHat-based systems still accept a
  hyphen. (EE-41)

### Fixed

- The end-to-end tests pass the repository client certificate to every
  deployment run. Hosts that never had the certificate installed failed to
  install pgEdge packages, because `install_repos` left the gated
  repositories disabled: the two nodes the Ultra-HA workflow adds to zone 1,
  and every host in both workflows' zone-join jobs, which wrote no
  certificate at all. Every job in both workflows now writes it from the
  `PGEDGE_REPO_CLIENT_CRT` and `PGEDGE_REPO_CLIENT_KEY` secrets with
  `tests/write-client-cert.sh`, and each workflow defines the arguments that
  pass it once, for all its jobs. The Ultra-HA idempotence checks after adding
  the nodes and after a switchover pass it as the deployment runs before them
  do.
  `tests/run-test.sh` passes the files named by `PGEDGE_CLIENT_CERT_SRC` and
  `PGEDGE_CLIENT_KEY_SRC`, and stops before building anything when either is
  unset or unreadable. (#73)

- Patroni replicas on Debian-based systems now start when `patroni_scope` is
  anything other than `<pg_version>-<cluster_name>`, such as the per-zone
  scope that [Sharing One Store Across Zones](../configuration/dcs.md#sharing-one-store-across-zones)
  recommends. Patroni built Debian replicas with the `pg_clonecluster_patroni`
  script from Debian's Patroni package, which derives the version and cluster
  name by splitting the scope at hyphens. With a scope such as `17-demo-zone1` it created a cluster named
  `zone1`, the replica's own configuration directory stayed empty, and
  `patronictl list` reported the replica as `start failed`. `setup_patroni`
  now installs `/usr/local/bin/patroni_debian_cluster`, written with
  `pg_version` and `cluster_name`, and Patroni uses it both to bootstrap a
  zone and to clone a replica. A configuration directory left behind by a
  node whose data is gone is cleared before the cluster is created again.
  (EE-41)
