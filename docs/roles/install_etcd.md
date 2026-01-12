# install_etcd

## Overview

The `install_etcd` role downloads and installs etcd distributed key-value store from GitHub releases. etcd is used by Patroni for distributed consensus and leader election in high availability PostgreSQL clusters.

## Purpose

The role performs the following tasks:

- Downloads etcd binary from official [GitHub releases](https://github.com/etcd-io/etcd/releases).
- Verifies download integrity using checksums.
- Installs etcd binaries to system directories.
- Creates etcd system user and group.
- Installs systemd service unit for etcd.
- Prepares etcd for cluster configuration.

## Role Dependencies

- `role_config`: Provides shared configuration variables

## When to Use

Execute this role on **pgedge hosts** in high availability configurations before installing Patroni:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
```

!!! important "HA Clusters Only"
    This role is only required for high availability deployments when you enable the `is_ha_cluster` parameter. Standalone PostgreSQL instances do not need etcd.

## Parameters

This role uses the following configuration parameters:

* `etcd_version`
* `etcd_base_url`
* `etcd_checksum`
* `etcd_package`
* `etcd_user`
* `etcd_group`
* `etcd_install_dir`
* `etcd_config_dir`
* `etcd_data_dir`

## Tasks Performed

### 1. Installation Check

- Checks if etcd binary already exists at `{{ etcd_install_dir }}/etcd`
- Skips installation if binary is present

### 2. System User Creation

- Creates `etcd_user` system user
- Sets home directory to `etcd_data_dir` for convenient data access
- Configures `/bin/bash` as shell
- Marks as system account
- Automatically creates data directory as user's home

### 3. Binary Download

- Creates temporary workspace in `~/tmp`
- Downloads etcd tarball from GitHub releases
- Verifies download using SHA256 checksum
- Ensures download integrity before installation

!!! info "GitHub Dependency"
    This role downloads binaries directly from GitHub releases. For air-gapped environments, configure a local mirror using `etcd_base_url`.

### 4. Binary Extraction and Installation

- Extracts downloaded tarball to temporary directory
- Copies binaries to `etcd_install_dir`
- Ensures binaries are executable (mode 0755)
- Installs three binaries:
  - `etcd` - Main etcd server
  - `etcdctl` - Command-line client for etcd
  - `etcdutl` - Utility for etcd maintenance

### 5. Systemd Service Installation

- Installs systemd service unit file
- Configures service to run as `etcd_user`
- Service is installed but not enabled or started
- Actual service configuration is performed by `setup_etcd` role

## Files Generated

### Directories

- `{{ etcd_install_dir }}` - Location for all etcd-related software
- `{{ etcd_config_dir }}` - Configuration location
- `{{ etcd_data_dir }}` - Directory for etcd database; also acts as `etcd_user` home

### Binaries

- `{{ etcd_install_dir }}/etcd` - etcd server binary
- `{{ etcd_install_dir }}/etcdctl` - etcd command-line client
- `{{ etcd_install_dir }}/etcdutl` - etcd maintenance utility

### System Files

- `/etc/systemd/system/etcd.service` - Systemd service unit

### Temporary Files

- `~/tmp/{{ etcd_package }}.tar.gz` - Downloaded archive
- `~/tmp/{{ etcd_package }}/` - Extracted files from archive

## Platform-Specific Behavior

### All Supported Platforms

This role is platform-agnostic as it installs pre-compiled binaries directly from GitHub. It should work identically on any systemd-based Linux distribution.

## Example Usage

### Basic Installation (HA Cluster)

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role: install_etcd
```

### Custom etcd Version

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_version: "3.5.12"
  roles:
    - install_etcd
```

### Air-Gapped Installation with Local Mirror

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_base_url: "https://mirror.internal.net/etcd/v{{ etcd_version }}"
    etcd_checksum: "sha256:{{ etcd_base_url }}/SHA256SUMS"
  roles:
    - install_etcd
```

### Custom Installation Directories

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_install_dir: "/opt/etcd"
    etcd_data_dir: "/data/etcd"
    etcd_config_dir: "/opt/etcd/config"
  roles:
    - install_etcd
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- check for existing etcd binary before installation.
- skip download and installation if etcd is already present.
- defer user management to the operating system.
- update the service file if the template changes.

## Notes

You should ensure etcd version is compatible with your Patroni version. etcd 3.4+ is recommended for Patroni 2.0+.
