# init_server

## Overview

The `init_server` role performs initial server preparation, installing required system packages, configuring system settings, creating necessary users, and setting up SSH keys for inter-node communication.

## Purpose

- Install required system packages
- Configure SELinux settings
- Set up core dump handling for debugging
- Manage `/etc/hosts` entries for all cluster nodes
- Create Postgres system user and group
- Create backup system user (for SSH backup mode)
- Generate and distribute SSH keys

## Role Dependencies

- `role_config` - Provides shared configuration variables

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

Installs required system packages:

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

- Checks current SELinux status
- Disables SELinux if `disable_selinux: true`
- Reboots the system if necessary
- Waits for the system to come back online

### 3. Core Dump Configuration

When `debug_pgedge: true`:

- Configures `systemd-coredump` settings
- Sets kernel parameters for core file generation
- Ensures unlimited core dump sizes
- Configures core file naming patterns

### 4. Host File Management

When `manage_host_file: true`:

- Collects facts about all hosts in the cluster
- Adds entries to `/etc/hosts` for each host
- Maps hostnames to IP addresses
- Ensures all nodes can resolve each other

### 5. User Creation

**Postgres User:**

- Creates `postgres` user and group
- Sets up home directory
- Generates ed25519 SSH key pair
- Configures SSH authorized keys and known hosts
- Stores SSH public keys on Ansible controller

**Backup User (SSH mode only):**

- Creates backup user (default: `backrest`)
- Sets up home directory
- Generates ed25519 SSH key pair
- Configures SSH authorized keys and known hosts
- Applies to hosts in the `backup` group

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

- Skip package installation if packages are present
- Not regenerate SSH keys if they exist
- Update `/etc/hosts` if new nodes are added
- Not reboot if SELinux is already in the desired state

## Troubleshooting

### Package Installation Failures

**Symptom:** Package installation fails with repository errors

**Solution:**

- Verify internet connectivity
- Check repository configuration
- Update package cache manually:
    - Debian: `apt update`
    - RHEL: `dnf makecache`

### SELinux Reboot Issues

**Symptom:** System doesn't come back online after SELinux configuration

**Solution:**

- Verify SSH connectivity is maintained through reboots
- Check firewall rules allow SSH
- Increase wait timeout in Ansible configuration
- Manually check system status after reboot

### SSH Key Problems

**Symptom:** SSH keys not properly generated or distributed

**Solution:**

- Verify `postgres` user exists
- Check permissions on `.ssh` directory (700)
- Check permissions on SSH keys (600 for private, 644 for public)
- Ensure Ansible has write access to `host-keys` directory

### Host File Issues

**Symptom:** Nodes cannot resolve each other's hostnames

**Solution:**

- Verify `/etc/hosts` contains all cluster nodes
- Check that `manage_host_file: true`
- Ensure inventory contains correct hostnames/IPs
- Test resolution: `ping hostname`

## Notes

!!! info "SSH Keys"
    SSH keys generated by this role are used by `setup_backrest` to establish trust between nodes for backup operations.

!!! warning "Reboots"
    This role may trigger system reboots when changing SELinux settings. Ensure your Ansible SSH connection can survive reboots.

## See Also

- [Configuration Reference](../configuration.md) - System configuration variables
- [Architecture](../architecture.md) - Understanding cluster topology
