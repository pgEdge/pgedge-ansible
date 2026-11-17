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

### Changed

### Fixed

- The end-to-end tests pass the repository client certificate to every
  deployment run. Hosts that never had the certificate installed failed to
  install pgEdge packages, because `install_repos` left the gated
  repositories disabled: the two nodes the Ultra-HA workflow adds to zone 1,
  and every host in both workflows' zone-join jobs, which wrote no
  certificate at all. The zone-join jobs now write it from the
  `PGEDGE_REPO_CLIENT_CRT` and `PGEDGE_REPO_CLIENT_KEY` secrets as the test
  jobs do, and the Ultra-HA idempotence checks after adding the nodes and
  after a switchover pass it as the deployment runs before them do.
  `tests/run-test.sh` passes the files named by `PGEDGE_CLIENT_CERT_SRC` and
  `PGEDGE_CLIENT_KEY_SRC`, and stops before building anything when either is
  unset or unreadable. (#73)
