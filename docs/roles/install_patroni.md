# install_patroni

## Overview

The `install_patroni` role installs Patroni, a high availability solution for PostgreSQL using Python and etcd for distributed consensus. Patroni manages automatic failover, leader election, and cluster configuration for PostgreSQL.

## Purpose

- Install pipx for isolated Python application management
- Install Patroni with required dependencies via pipx
- Configure Patroni as postgres OS user
- Install systemd service unit for Patroni
- Create Patroni configuration directory
- Prepare system for HA PostgreSQL cluster management

## Role Dependencies

- `role_config` - Provides shared configuration variables
- `init_server` - Must create postgres user first
- `install_pgedge` - PostgreSQL must be installed

## When to Use

Execute this role on **pgedge hosts** in high availability configurations after installing PostgreSQL and etcd:

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
    Patroni is only required for high availability deployments where `is_ha_cluster: true`. Standalone PostgreSQL instances do not need Patroni.

## Parameters

This role uses the following configuration parameters:

* `patroni_bin_dir`
* `patroni_config_dir`

## Tasks Performed

### 1. Installation Check

- Checks if Patroni binary already exists at `{{ patroni_bin_dir }}/patroni`
- Runs as postgres OS user to check user-specific installation
- Skips installation if Patroni is already present

### 2. Package Prerequisites

!!! info "pipx Isolation"
    This role currently uses pipx for installing Patroni and dependencies.
    Using pipx creates an isolated Python environment for Patroni, preventing conflicts with system Python packages. This is especially important on Debian 12+ which restricts system-wide pip installations.

**Debian/Ubuntu Systems:**

- Installs `pipx` package via APT
- Ensures pipx is available system-wide

**RHEL/Rocky Linux Systems:**

- Installs `python3-pip` via DNF
- Installs pipx using pip3 as root
- Creates pipx environment for postgres OS user
- Ensures postgres user has pipx in PATH

### 3. Patroni Installation

- Installs Patroni via pipx as postgres user
- Includes required extras:
  - `psycopg2-binary` - PostgreSQL database adapter
  - `etcd` - etcd client library for distributed consensus
- Creates isolated Python environment
- Installs binaries to `patroni_bin_dir`
- Sources bash profile for proper environment setup

### 4. Systemd Service Installation

- Installs systemd service unit file
- Configures service to run as postgres user
- Sets up proper dependencies and startup order
- Service is installed but not enabled or started
- Actual service configuration is performed by `setup_patroni` role

!!! note "Service Management"
    This role installs the systemd service but does not enable or start it. The `setup_patroni` role handles service configuration and startup.

### 5. Configuration Directory Creation

- Creates `patroni_config_dir` directory
- Sets ownership to `postgres:postgres`
- Applies secure permissions (mode `0700`)
- Prepares location for Patroni YAML configuration

## Files Generated

### Binaries (via pipx)

- `{{ patroni_bin_dir }}/patroni` - Patroni main binary
- `{{ patroni_bin_dir }}/patronictl` - Patroni control utility
- `{{ pg_home }}/.local/share/pipx/venvs/patroni/` - Isolated Python environment

### System Files and Directories

- `/etc/systemd/system/patroni.service` - Systemd service unit
- `{{ patroni_config_dir }}/` - Configuration directory (empty, populated by setup_patroni)

### User Environment

- Updates postgres user's PATH to include pipx binaries
- Integrates with `.bash_profile` and `.bashrc`

## Platform-Specific Behavior

### Debian-Family

- Installs pipx from system packages (`pipx` package)
- pipx is managed by APT and available to all users
- Uses pipx to install Patroni and prerequisite libraries
- Patroni installs to `/var/lib/postgresql/.local/bin` by default (`patroni_bin_dir`)

### RHEL-Family

- Installs `python3-pip` first
- Uses pip to install pipx to postgres user's environment
- Uses pipx to install Patroni and prerequisite libraries
- Patroni installs to `/var/lib/pgsql/.local/bin` by default (`patroni_bin_dir`)

## Example Usage

### Basic Installation (HA Cluster)

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

### Standalone Installation with Custom Binaries Location

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    patroni_bin_dir: "/opt/patroni/bin"
  roles:
    - install_patroni
```

## Idempotency

This role is fully idempotent:

- Checks for existing Patroni binary before installation
- Skips pipx installation if already present
- System packages are maintained by the operating system once installed
- Service file is updated if template changes
- Safe to re-run multiple times

## Troubleshooting

### pipx Installation Fails

**Symptom:** Failed to install pipx on RHEL systems

**Solution:**

- Verify Python 3 and pip are installed:

```bash
python3 --version
pip3 --version
```

- Manually install pipx as the postgres user:

```bash
sudo -u postgres python3 -m pip install --user pipx
sudo -u postgres python3 -m pipx ensurepath
```

- Verify pipx is in PATH:

```bash
pipx --version
```

### Patroni Installation Fails

**Symptom:** pipx install patroni command fails

**Solution:**

- Check postgres user's environment:

```bash
sudo -u postgres pipx list
```

- Verify pipx environment is initialized:

```bash
sudo -u postgres pipx ensurepath
```

- Check for compilation errors (missing development packages):

```bash
# Debian/Ubuntu
sudo apt install python3-dev libpq-dev

# RHEL/Rocky
sudo dnf install python3-devel postgresql-devel
```

### Binary Not Found After Installation

**Symptom:** patroni command not found

**Solution:**

- Verify installation location:

```bash
sudo -i -u postgres ls -la .local/bin/
```

- Check PATH includes `patroni_bin_dir`:

```bash
sudo -i -u postgres printenv | grep PATH
```

- Manually add to PATH to `.profile`, `.bash_profile`, or `.bashrc` files:

```bash
export PATH="$PATH:/var/lib/pgsql/.local/bin"
```

### Permission Denied on Config Directory

**Symptom:** Cannot write to `/etc/patroni`

**Solution:**

- Verify directory ownership:

```bash
sudo ls -la /etc/patroni
```

- Fix permissions:

```bash
sudo chown postgres:postgres /etc/patroni
sudo chmod 700 /etc/patroni
```

### Service File Not Loaded

**Symptom:** systemd doesn't recognize patroni service

**Solution:**

- Verify service file exists:

```bash
ls -la /etc/systemd/system/patroni.service
```

- Reload systemd daemon:

```bash
sudo systemctl daemon-reload
```

- Check service status:

```bash
sudo systemctl status patroni
```

### psycopg2 Build Fails

**Symptom:** Failed to build psycopg2-binary during installation

**Solution:**

- Install required development packages:

```bash
# Debian/Ubuntu
sudo apt install gcc python3-dev libpq-dev

# RHEL/Rocky
sudo dnf install gcc python3-devel postgresql-devel
```

- Retry Patroni installation:

```bash
sudo -u postgres pipx install patroni[psycopg2-binary,etcd]
```

## Notes

After installation, verify Patroni is installed correctly:

```bash
sudo -i -u postgres patroni --version
sudo -i -u postgres patronictl version
```

## See Also

- [Configuration Reference](../configuration.md) - Patroni configuration variables
- [Architecture](../architecture.md) - Understanding HA cluster topology
- [setup_patroni](setup_patroni.md) - Configures and starts Patroni cluster
- [install_etcd](install_etcd.md) - Installs etcd required by Patroni
- [install_pgedge](install_pgedge.md) - Installs PostgreSQL managed by Patroni
