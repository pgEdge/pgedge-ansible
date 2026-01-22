# install_etcd

The `install_etcd` role downloads and installs etcd, a distributed key-value
store that Patroni uses for consensus and leader election in high availability
Postgres clusters.

The role performs the following tasks on inventory hosts:

- Download etcd binaries from official GitHub releases.
- Verify download integrity using SHA256 checksums.
- Install etcd binaries to the system directory.
- Create the etcd system user and group.
- Install the systemd service unit for etcd.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

Execute this role on pgedge hosts in high availability configurations before
installing Patroni.

In the following example, the playbook installs etcd as part of a high
availability cluster deployment:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - install_patroni
```

!!! important "HA Clusters Only"
    Only high availability deployments need this role; set the `is_ha_cluster`
    parameter to `true` to enable HA mode. Standalone Postgres instances do
    not need etcd.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    etcd_version: "3.5.12"
    etcd_install_dir: /usr/local/bin
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `etcd_version` | Specify the etcd version to download and install. |
| `etcd_base_url` | Override the download URL for air-gapped environments. |
| `etcd_checksum` | Specify the checksum URL or value for verification. |
| `etcd_package` | Override the package name for custom builds. |
| `etcd_user` | Specify the system user that runs etcd. |
| `etcd_group` | Specify the system group for etcd. |
| `etcd_install_dir` | Set the directory for etcd binaries. |
| `etcd_config_dir` | Set the directory for etcd configuration files. |
| `etcd_data_dir` | Set the directory for etcd database storage. |

## How It Works

The role downloads etcd from GitHub releases and installs the binaries to
the system.

1. Check for existing installation.
    - Check whether the etcd binary exists at `{{ etcd_install_dir }}/etcd`.
    - Skip the installation process when the role finds an existing binary.

2. Create the system user.
    - Create the `etcd_user` system account for running etcd.
    - Set the home directory to `etcd_data_dir` for data access.
    - Configure `/bin/bash` as the shell and mark as a system account.
    - Create the data directory automatically as the user home.

3. Download etcd binaries.
    - Create a temporary workspace in `~/tmp`.
    - Download the etcd tarball from GitHub releases.
    - Verify the download using the SHA256 checksum.

4. Install etcd binaries.
    - Extract the downloaded tarball to the temporary directory.
    - Copy the `etcd`, `etcdctl`, and `etcdutl` binaries to `etcd_install_dir`.
    - Set executable permissions with mode 0755.

5. Install the systemd service.
    - Install the systemd service unit file at 
      `/etc/systemd/system/etcd.service`.
    - Configure the service to run as `etcd_user`.
    - Leave the service disabled; `setup_etcd` handles service configuration.

!!! info "GitHub Dependency"
    This role downloads binaries directly from GitHub releases. For
    air-gapped environments, configure a local mirror using `etcd_base_url`.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook installs etcd using default settings:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
```

### Custom etcd Version

In the following example, the playbook installs a specific etcd version:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_version: "3.5.12"
  roles:
    - install_etcd
```

### Air-Gapped Installation

In the following example, the playbook uses a local mirror for etcd binaries:

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

In the following example, the playbook specifies custom paths for etcd:

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

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ etcd_install_dir }}/etcd` | New | Main etcd server binary. |
| `{{ etcd_install_dir }}/etcdctl` | New | Command-line client for etcd administration. |
| `{{ etcd_install_dir }}/etcdutl` | New | Utility for etcd maintenance operations. |
| `/etc/systemd/system/etcd.service` | New | Systemd service unit for etcd. |
| `{{ etcd_config_dir }}/` | New | Configuration directory for etcd settings. |
| `{{ etcd_data_dir }}/` | New | Data directory for etcd database storage. |

## Platform-Specific Behavior

This role is platform-agnostic because it installs pre-compiled binaries
directly from GitHub. The role works identically on any systemd-based Linux
distribution.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Skip the download and installation when the etcd binary exists.
- Defer user management to the operating system when the user exists.

The role may update these items on subsequent runs:

- Update the systemd service file when the template changes.
