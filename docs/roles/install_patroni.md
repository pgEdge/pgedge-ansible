# install_patroni

The `install_patroni` role installs Patroni, a high availability solution for
Postgres that uses etcd for distributed consensus. Patroni manages automatic
failover, leader election, and cluster configuration.

The role performs the following tasks on inventory hosts:

- Install pipx for isolated Python application management.
- Install Patroni with necessary dependencies via pipx.
- Configure Patroni as the postgres OS user.
- Install the systemd service unit for Patroni.
- Create the Patroni configuration directory.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` creates the postgres user that the installation process needs.
- `install_pgedge` installs Postgres before Patroni can manage the cluster.

## When to Use

Execute this role on pgedge hosts in high availability configurations after
installing Postgres and etcd.

In the following example, the playbook installs Patroni as part of a high
availability cluster deployment:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_pgedge
    - install_etcd
    - install_patroni
```

!!! important "HA Clusters Only"
    Only high availability deployments need Patroni; set the `is_ha_cluster`
    parameter to `true` to enable HA mode. Standalone Postgres instances do
    not need Patroni.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    patroni_bin_dir: /var/lib/postgresql/.local/bin
    patroni_config_dir: /etc/patroni
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `patroni_bin_dir` | Set the directory for Patroni binaries. |
| `patroni_config_dir` | Set the directory for Patroni configuration files. |

## How It Works

The role installs Patroni using pipx to create an isolated Python environment
that prevents conflicts with system packages.

1. Check for existing installation.
    - Check whether the Patroni binary exists at 
      `{{ patroni_bin_dir }}/patroni`.
    - Run the check as the postgres OS user for user-specific installations.
    - Skip the installation process when the role finds an existing binary.

2. Install package prerequisites.
    - Install the `pipx` package via APT on Debian-family systems.
    - Install `python3-pip` via DNF on RHEL-family systems.
    - Install pipx using pip3 for the postgres user on RHEL systems.

3. Install Patroni via pipx.
    - Install Patroni as the postgres user for proper ownership.
    - Include the `psycopg2-binary` extra for Postgres connectivity.
    - Include the `etcd` extra for distributed consensus support.
    - Create an isolated Python environment in the user home directory.

4. Install the systemd service.
    - Install the systemd service unit at 
      `/etc/systemd/system/patroni.service`.
    - Configure the service to run as the postgres user.
    - Leave the service disabled; `setup_patroni` handles service startup.

5. Create the configuration directory.
    - Create the `patroni_config_dir` directory for YAML configuration.
    - Set ownership to `postgres:postgres` for proper access.
    - Apply secure permissions with mode 0700.

!!! info "pipx Isolation"
    Using pipx creates an isolated Python environment for Patroni. This
    approach prevents conflicts with system Python packages and Debian 12+
    requires pipx because the system restricts system-wide pip installations.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook installs Patroni for a high
availability cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_pgedge
    - install_etcd
    - install_patroni
```

### Custom Binary Location

In the following example, the playbook specifies a custom directory for
Patroni binaries:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    patroni_bin_dir: "/opt/patroni/bin"
  roles:
    - install_patroni
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ patroni_bin_dir }}/patroni` | New | Main Patroni binary for cluster management. |
| `{{ patroni_bin_dir }}/patronictl` | New | Patroni control utility for administration. |
| `/etc/systemd/system/patroni.service` | New | Systemd service unit for Patroni. |
| `{{ patroni_config_dir }}/` | New | Configuration directory; populated by `setup_patroni`. |
| `{{ pg_home }}/.local/share/pipx/venvs/patroni/` | New | Isolated Python environment for Patroni. |

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, the role uses these paths and packages:

| Setting | Value |
|---------|-------|
| pipx package | `pipx` via APT |
| Patroni binary path | `/var/lib/postgresql/.local/bin` |
| Python environment | `~postgres/.local/share/pipx/venvs/patroni/` |

### RHEL Family

On RHEL-based systems, the role uses these paths and packages:

| Setting | Value |
|---------|-------|
| pipx installation | `pip3 install pipx` as root |
| Patroni binary path | `/var/lib/pgsql/.local/bin` |
| Python environment | `~postgres/.local/share/pipx/venvs/patroni/` |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Skip the Patroni installation when the binary exists.
- Skip pipx installation when the system already has pipx.
- Defer package maintenance to the operating system.

The role may update these items on subsequent runs:

- Update the systemd service file when the template changes.
