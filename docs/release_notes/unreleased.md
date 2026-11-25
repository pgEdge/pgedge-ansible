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

`init_server` now writes its systemd settings to drop-in files under
`/etc/systemd/` rather than editing the main configuration files there; see
[Fixed](#fixed). On a host deployed by an earlier release, the lines those
releases added stay where they are: `RemoveIPC=no` in
`/etc/systemd/logind.conf`, and with `debug_pgedge`, the `ANSIBLE MANAGED`
block in `/etc/systemd/coredump.conf` and `DefaultLimitCORE` in
`/etc/systemd/system.conf`. They set the same values as the drop-ins, so they
do no harm and can stay or be removed. The first run after upgrading creates
the drop-ins and restarts `systemd-logind` once.

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
      where their packages ship a newer version. One whose package has no
      update path from the installed version is reported and left as it is.
    - The HAProxy hosts follow, one at a time.
    - pgBackRest is updated last, on every pgEdge node and backup server at
      once, because a client and repository host on different versions
      refuse each other. A running backup stops it.

  The run reports what it will update, and in what order, before it stops
  anything. It refuses to start when `pg_allow_restart` is `false`, or when
  `etcd_version` is an earlier minor release than a node runs or more than
  one minor release past it. A run that stops partway resumes where it
  stopped, and every run first repairs what a cancelled one may have left,
  such as the owner of `/var/log/pgbackrest`. A run with nothing to update
  changes nothing. A service still running libraries that an operating system
  update replaced is restarted too, in the same order, even when no package
  the collection installed changed. (#76)

### Changed

- `etcd_version` and `etcd_install_dir` are defaults of `role_config` rather
  than of `install_etcd` and `setup_etcd`, so `update_software` can compare a
  node's etcd with the release the collection installs. Their meaning is
  unchanged. (#76)

- `etcd_version` defaults to 3.6.17 rather than 3.6.5. A new node gets 3.6.17.
  A deployed node keeps its etcd until a run with `permit_software_updates`
  brings it to the new default, one node at a time. An inventory that sets
  `etcd_version` keeps its own release. (#76)

- `spock_version` defaults to `5.0` rather than `5.0.4`, and is documented as
  reserved for future use. It will name the major version of Spock to install.
  No role reads it yet, and the newest Spock the repositories offer is still
  installed. (#76)

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

- `init_server` works on Rocky Linux 10 and other EL10 distributions. Their
  systemd keeps its default configuration in `/usr/lib/systemd/` and installs
  no `logind.conf`, `coredump.conf` or `system.conf` in `/etc/systemd/`, so
  the task that disables `RemoveIPC` stopped every deployment with
  "Destination /etc/systemd/logind.conf does not exist", and with
  `debug_pgedge`, the default, the core dump settings would have failed the
  same way. The role now writes each setting to a drop-in file named
  `50-pgedge.conf` in `/etc/systemd/logind.conf.d/`,
  `/etc/systemd/coredump.conf.d/` and `/etc/systemd/system.conf.d/`, which
  every supported distribution reads. Rocky Linux 10 joins the validated
  platforms. The e2e tests gain Rocky 10 images and a `rocky10` choice for
  the workflows' `os` input. (#80)

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

- `finalize_backrest` no longer fails on a zone whose primary is on timeline
  10 or later. To check that the newest backup can restore the cluster, it
  reads the current timeline's history file, and it built the file's name
  with `to_hex()`, which returns lowercase hex. Postgres names history files
  in uppercase, so from timeline 10 the role asked for `0000000a.history`
  while the file was `0000000A.history`, and the deployment playbook failed.
  Every switchover or failover moves a zone to a new timeline, so a zone
  reached this after nine of them. The role now folds the name to uppercase,
  and so does the end-to-end check in `tests/verify/verify-commit.yml` that
  reads the same file. (#77)
