# init_server

## Overview

The `init_server` role performs initial server preparation, installing required system packages, configuring system settings, creating necessary users, and setting up SSH keys for inter-node communication.

## Purpose

This role performs the following tasks:

- Installs required system packages on all hosts.
- Configures SELinux settings according to deployment needs.
- Establishes core dump handling for debugging purposes.
- Manages `/etc/hosts` entries for all cluster nodes.
- Creates the Postgres system user and group.
- Creates a backup system user for SSH backup mode.
- Generates and distributes SSH keys among nodes.

## Role Dependencies

- `role_config`: Provides shared configuration variables

## When to Use

Execute this role on **all hosts** in your cluster as the first step of any deployment:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

!!! important "Execution Order"
    Always run `init_server` before any other roles. It establishes the foundation for the entire deployment.

## Parameters

This role uses the following configuration parameters:

### Role Configuration

* `debug_pgedge`
* `disable_selinux`
* `manage_host_file`

### pgEdge Server Related

* `pg_home`

### Backup Server Related

* `backup_repo_path`
* `backup_repo_user`

## Tasks Performed

### 1. Package Installation

The role installs the following required system packages:

**Common packages (all systems):**

- `acl` - Access control lists necessary for Ansible temporary files
- `jq` - JSON processor for useful status checks
- `nano` - Common text editor
- `less` - "Less is more"
- `rsync` - File synchronization
- `python3-cryptography` - Ansible dependency

**RHEL-specific:**

- `kernel-modules-extra` - Additional kernel modules for core dumps

**Debian-specific:**

- `systemd-coredump` - Core dump management

### 2. SELinux Configuration

The role performs the following SELinux configuration tasks:

- checks the current SELinux status.
- disables SELinux when you enable the `disable_selinux` parameter.
- reboots the system if necessary.
- waits for the system to come back online.

### 3. Core Dump Configuration

When you enable the `debug_pgedge` parameter, the role:

- configures `systemd-coredump` settings.
- sets kernel parameters for core file generation.
- ensures unlimited core dump sizes.
- configures core file naming patterns.

### 4. Host File Management

When you enable the `manage_host_file` parameter, the role:

- collects facts about all hosts in the cluster.
- adds entries to `/etc/hosts` for each host.
- maps hostnames to IP addresses.
- ensures all nodes can resolve each other.

### 5. User Creation

**Postgres User:**

The role performs the following tasks for the postgres user:

- creates the `postgres` user and group.
- sets up the home directory.
- generates an ed25519 SSH key pair.
- configures SSH authorized keys and known hosts.
- stores SSH public keys on the Ansible controller.

**Backup User (SSH mode only):**

The role performs the following tasks for the backup user for hosts in the `backup` group:

- creates the backup user (default: `backrest`).
- sets up the home directory.
- generates an ed25519 SSH key pair.
- configures SSH authorized keys and known hosts.

## Files Generated

### On Target Hosts

On servers in the `pgedge` group:

- `{{ pg_home }}/.ssh/id_ed25519` - Postgres user SSH private key
- `{{ pg_home }}/.ssh/id_ed25519.pub` - Postgres user SSH public key
- `{{ pg_home }}/.ssh/authorized_keys` - Authorized keys for Postgres user

On servers in the `backup` group:

- `{{ backup_repo_path }}/.ssh/id_ed25519` - Backup user SSH private key
- `{{ backup_repo_path }}/.ssh/id_ed25519.pub` - Backup user SSH public key
- `{{ backup_repo_path }}/.ssh/authorized_keys` - Authorized keys for Backup user

### On Ansible Controller

- `host-keys/{{ inventory_hostname }}` - Principle host key for the listed server

These keys are used by later roles to set up SSH trust relationships.

## Files Modified

- `/etc/hosts` - Updated with cluster node entries
- `/etc/systemd/logind.conf` - Disables `RemoveIPC` setting to prevent service disruption

When Core dumps are enabled:

- `/etc/security/limits.conf` - Instructs PAM to allow unlimited core files
- `/etc/systemd/coredump.conf` - Limits total stored core files to 64GB
- `/etc/systemd/system.conf` - Set systemd to allow unlimited core files

## Platform-Specific Behavior

### Debian

- Uses `apt` package manager
- Installs `systemd-coredump` package

### RHEL

- Uses `dnf` package manager
- Installs `kernel-modules-extra` package

## Example Usage

### Basic Initialization

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

### With Custom Parameters

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - role: init_server
      vars:
        debug_pgedge: false
        manage_host_file: false
        disable_selinux: false
```

### Initialization for Different Groups

```yaml
# Initialize all pgEdge nodes
- hosts: pgedge
  roles:
    - init_server

# Initialize HAProxy nodes
- hosts: haproxy
  roles:
    - init_server

# Initialize backup servers
- hosts: backup
  roles:
    - init_server
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- skip package installation if packages are present.
- not regenerate SSH keys if they exist.
- update `/etc/hosts` if new nodes are added.
- not reboot if SELinux is already in the desired state.

## Notes

!!! info "SSH Keys"
    SSH keys generated by this role are used by `setup_backrest` to establish trust between nodes for backup operations.

!!! warning "Reboots"
    This role may trigger system reboots when changing SELinux settings. Ensure your Ansible SSH connection can survive reboots.
