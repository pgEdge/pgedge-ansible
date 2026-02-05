# init_server

The `init_server` role performs initial server preparation for pgEdge cluster
deployments. It installs required system packages, configures system settings,
creates necessary users, and sets up SSH keys for inter-node communication.

This role performs the following tasks on inventory hosts:

- Install required system packages for Ansible and cluster operations.
- Configure SELinux settings according to deployment needs.
- Establish core dump handling for debugging purposes.
- Manage `/etc/hosts` entries for all cluster nodes.
- Create the Postgres system user and group.
- Create a backup system user for SSH backup mode.
- Generate and distribute SSH keys among cluster nodes.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables.

## When to Use

Execute this role on all hosts in your cluster as the first step of any
deployment.

In the following example, the playbook runs `init_server` on all hosts:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

!!! important "Execution Order"
    Always run `init_server` before any other roles; it establishes the
    foundation for the entire deployment.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    debug_pgedge: true
    disable_selinux: true
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `debug_pgedge` | Enable core dump collection for debugging. |
| `disable_selinux` | Disable SELinux on RHEL-based systems. |
| `manage_host_file` | Manage `/etc/hosts` entries for cluster nodes. |
| `pg_home` | Home directory path for the Postgres user. |
| `backup_repo_path` | Home directory path for the backup user. |
| `backup_repo_user` | Username for the backup system account. |

## How It Works

This role operates in several phases to prepare servers for cluster deployment.

### Package Installation

This role installs required system packages on all target hosts. The following
common packages apply to all systems:

- `acl` provides access control lists for Ansible temporary files.
- `jq` provides JSON processing for status checks.
- `nano` provides a text editor for configuration management.
- `less` provides a pager utility for viewing output.
- `rsync` provides file synchronization for backup operations.
- `python3-cryptography` provides cryptography support for Ansible.

On RHEL-based systems, this role also installs these packages:

- `kernel-modules-extra` provides additional kernel modules for core dumps.

On Debian-based systems, this role also installs these packages:

- `systemd-coredump` provides core dump management.

### SELinux Configuration

When you enable the `disable_selinux` parameter, this role performs these
SELinux configuration tasks:

1. Check the current SELinux status.
    - Query the current SELinux enforcement mode.
    - Determine if a configuration change is required.

2. Disable SELinux when required.
    - Modify the SELinux configuration file.
    - Set the enforcement mode to disabled.

3. Reboot the system.
    - Reboot the system to apply the SELinux changes.
    - Wait for the system to return to an available state.

### Core Dump Configuration

When you enable the `debug_pgedge` parameter, this role configures the system
for core dump collection:

1. Configure `systemd-coredump` settings.
    - Set appropriate storage limits for core files.
    - Configure core file naming patterns.

2. Set kernel parameters.
    - Enable unlimited core dump sizes.
    - Configure process limits for core generation.

### Host File Management

When you enable the `manage_host_file` parameter, this role manages the
`/etc/hosts` file:

1. Collect cluster host facts.
    - Gather facts about all hosts in the cluster.
    - Map hostnames to IP addresses.

2. Update the hosts file.
    - Add entries to `/etc/hosts` for each host.
    - Ensure all nodes can resolve each other by hostname.

### User Creation

This role creates system users required for cluster operations.

1. Create the Postgres user.
    - Create the `postgres` user and group.
    - Set up the home directory at the specified path.
    - Generate an ed25519 SSH key pair.
    - Configure SSH authorized keys and known hosts.
    - Store SSH public keys on the Ansible controller.

2. Create the backup user when hosts are in the `backup` group.
    - Create the backup user with the configured username.
    - Set up the home directory at the specified path.
    - Generate an ed25519 SSH key pair.
    - Configure SSH authorized keys and known hosts.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Initialization

In the following example, the playbook initializes all hosts with defaults:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

### Custom Parameters

In the following example, the playbook disables optional features:

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

In the following example, the playbook initializes different host groups:

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

## Artifacts

During execution, this role generates and modifies the following files on
inventory hosts.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ pg_home }}/.ssh/id_ed25519` | New | SSH private key for the Postgres user. |
| `{{ pg_home }}/.ssh/id_ed25519.pub` | New | SSH public key for the Postgres user. |
| `{{ pg_home }}/.ssh/authorized_keys` | New | Authorized keys file for SSH access. |
| `{{ backup_repo_path }}/.ssh/id_ed25519` | New | SSH private key for the backup user. |
| `{{ backup_repo_path }}/.ssh/id_ed25519.pub` | New | SSH public key for the backup user. |
| `{{ backup_repo_path }}/.ssh/authorized_keys` | New | Authorized keys file for backup user SSH access. |
| `host-keys/{{ inventory_hostname }}` | New | Host key stored on the Ansible controller. |
| `/etc/hosts` | Modified | Updated with cluster node entries. |
| `/etc/systemd/logind.conf` | Modified | Disables `RemoveIPC` setting to prevent disruption. |
| `/etc/security/limits.conf` | Modified | Configures PAM to allow unlimited core files. |
| `/etc/systemd/coredump.conf` | Modified | Limits total stored core files to 64GB. |
| `/etc/systemd/system.conf` | Modified | Sets systemd to allow unlimited core files. |

## Platform-Specific Behavior

This role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, this role performs these actions:

- Uses the `apt` package manager for package installation.
- Installs the `systemd-coredump` package for core dump management.

### RHEL Family

On RHEL-based systems, this role performs these actions:

- Uses the `dnf` package manager for package installation.
- Installs the `kernel-modules-extra` package for core dumps.
- Manages SELinux configuration when enabled.

## Idempotency

This role operates idempotently; you can safely re-run it on inventory hosts.

This role skips these operations when the target already exists:

- Package installation when packages are already present.
- SSH key generation when keys already exist.
- User creation when users already exist.

This role may update these items on subsequent runs:

- Update `/etc/hosts` when you add new nodes to the cluster.
- Reboot only when SELinux state requires a change.

!!! info "SSH Keys"
    The `setup_backrest` role uses SSH keys generated by this role to establish
    trust between nodes for backup operations.

!!! warning "Reboots"
    This role may trigger system reboots when changing SELinux settings. Ensure
    your Ansible SSH connection can survive reboots.
