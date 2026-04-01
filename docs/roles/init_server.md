# init_server

The `init_server` role performs initial server preparation for pgEdge cluster
deployments. It installs required system packages, configures system settings,
creates necessary users, and sets up SSH keys for inter-node communication.

This role performs the following tasks on inventory hosts:

- Install required system packages for Ansible and cluster operations.
- Configure SELinux settings according to deployment needs.
- Establish core dump handling for debugging purposes.
- Manage `/etc/hosts` entries for all cluster nodes.
- Disable `RemoveIPC` in systemd-logind to prevent shared memory segments
  from being removed when a user session ends.
- Create the `postgres` OS user and generate an SSH key pair for backup
  operations.
- Create a backup OS user on dedicated backup nodes.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables.

## When to Use

Execute this role on all hosts in your cluster as the first step of any
deployment. Always run `init_server` before any other roles; it establishes
the foundation for the entire deployment.

In the following example, the playbook runs `init_server` on all hosts:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `debug_pgedge` | Enable core dump collection for debugging. |
| `disable_selinux` | Disable SELinux on RHEL-based systems. |
| `manage_host_file` | Manage `/etc/hosts` entries for cluster nodes. |
| `pg_home` | Home directory path for the postgres OS user. |
| `backup_repo_path` | Home directory path for the backup OS user. |
| `backup_repo_user` | Username for the backup system account. |

See the [Configuration Reference](../configuration.md) for a complete list
of available parameters.

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

On RHEL-based systems, this role also installs `kernel-modules-extra` to
provide additional kernel modules for core dumps. On Debian-based systems,
this role installs `systemd-coredump` for core dump management.

### SELinux Configuration

When you enable `disable_selinux`, this role modifies the SELinux
configuration file, sets enforcement to disabled, and reboots the system to
apply the change. The role only reboots when the SELinux state requires a
change.

### Core Dump Configuration

When you enable `debug_pgedge`, this role configures `systemd-coredump`
settings, sets appropriate storage limits, and configures kernel parameters
to allow unlimited core dump sizes.

### RemoveIPC

This role disables the `RemoveIPC` setting in `systemd-logind.conf`. This
prevents systemd from removing shared memory segments when a user session
ends, which can disrupt running Postgres instances. The logind service
restarts only if the setting was changed.

### Host File Management

When you enable `manage_host_file`, this role gathers facts about all hosts
in the cluster, maps hostnames to IP addresses, and adds entries to
`/etc/hosts` on every node so all nodes can resolve each other by hostname.

### User Creation

This role creates the `postgres` OS user and generates an ed25519 SSH key
pair. On dedicated backup nodes, the role also creates the backup OS user
with the name specified in `backup_repo_user`.

## Usage Examples

In the following example, the playbook initializes all hosts with defaults:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server
```

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

## Artifacts

During execution, this role generates and modifies the following files on
inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ pg_home }}/.ssh/id_ed25519` | New | SSH private key for the postgres OS user. |
| `{{ pg_home }}/.ssh/id_ed25519.pub` | New | SSH public key for the postgres OS user. |
| `{{ pg_home }}/.ssh/authorized_keys` | New | Authorized keys file for SSH access. |
| `{{ backup_repo_path }}/.ssh/id_ed25519` | New | SSH private key for the backup OS user. |
| `{{ backup_repo_path }}/.ssh/authorized_keys` | New | Authorized keys file for backup user SSH access. |
| `/etc/hosts` | Modified | Updated with cluster node entries. |
| `/etc/systemd/logind.conf` | Modified | Disables `RemoveIPC` to prevent shared memory disruption. |
| `/etc/security/limits.conf` | Modified | Configures PAM to allow unlimited core files. |
| `/etc/systemd/coredump.conf` | Modified | Limits total stored core files to 64 GB. |

## Platform-Specific Behavior

On Debian-based systems, this role uses `apt` for package installation and
installs `systemd-coredump` for core dump management. On RHEL-based systems,
this role uses `dnf`, installs `kernel-modules-extra` for core dumps, and
manages SELinux configuration when enabled.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role skips
SSH key generation and user creation when the targets already exist. The role
may update `/etc/hosts` when you add new nodes to the cluster and reboots
only when SELinux state requires a change.

!!! info "SSH Keys"
    The `setup_backrest` role uses SSH keys generated by this role to establish
    trust between nodes for backup operations.

!!! warning "Reboots"
    This role may trigger system reboots when changing SELinux settings. Ensure
    your Ansible SSH connection can survive reboots.
