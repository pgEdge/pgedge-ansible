# install_repos

The `install_repos` role configures official pgEdge package repositories on
target systems. The role enables installation of pgEdge Enterprise Postgres
packages and adds EPEL on RHEL-based systems to satisfy dependencies.

The role performs the following tasks on inventory hosts:

- Install prerequisite packages for repository management.
- Add pgEdge package repositories for the target operating system.
- Configure the EPEL repository on RHEL-based systems.
- Import and verify GPG keys for package signing.
- Update the package cache to make pgEdge packages available.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares systems before repository installation.

## When to Use

Execute this role on all hosts where you will install pgEdge Postgres
packages. Run this role before any package installation roles.

In the following example, the playbook configures repositories on all
pgedge hosts:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Configuration

This role uses no custom parameters. The role handles all repository
configuration automatically based on the detected operating system.

## How It Works

The role configures package repositories based on the operating system
family that it detects on each target host.

### Debian Family Setup

On Debian-based systems, the role performs these steps:

1. Install prerequisite packages.
    - Install `curl` for downloading repository packages.
    - Install `gnupg2` for GPG key verification.
    - Install `lsb-release` for OS version detection.

2. Configure the pgEdge repository.
    - Download and install the pgEdge repository definition package.
    - Update the APT package cache to include pgEdge packages.
    - Configure automatic repository sources in `/etc/apt/sources.list.d/`.

### RHEL Family Setup

On RHEL-based systems, the role performs these steps:

1. Install the EPEL repository.
    - Enable EPEL via DNF configuration manager on RHEL 8 and 9.
    - Enable EPEL via subscription manager on RHEL 10.
    - Install EPEL from existing repos on Rocky and AlmaLinux 8+.
    - Install the Fedora EPEL package on Oracle Linux 8+.

2. Configure the pgEdge repository.
    - Import the pgEdge GPG key for package verification.
    - Download and install the pgEdge repository definition package.
    - Configure the YUM/DNF repository in `/etc/yum.repos.d/`.

!!! important "Execution Order"
    Execute this role before any `install_*` roles that install pgEdge
    packages. The role establishes the package sources that all subsequent
    installations need.

!!! warning "EPEL Dependencies"
    RHEL-based systems need EPEL for several Postgres dependencies. The role
    handles EPEL installation automatically but may need subscription access
    on RHEL systems.

!!! note "Network Requirements"
    This role requires outbound HTTPS access to pgEdge repository servers.
    Ensure firewall rules and proxy settings allow this connectivity.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook configures pgEdge repositories on
target hosts:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

### Multiple Node Groups

In the following example, the playbook configures repositories on Postgres
nodes and backup servers:

```yaml
# Install repos on all Postgres nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos

# Install repos on backup servers
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Artifacts

This role generates files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/apt/sources.list.d/pgedge.sources` | New | pgEdge repository configuration on Debian systems. |
| `/etc/apt/keyrings/pgedge.gpg` | New | Public pgEdge GPG key on Debian systems. |
| `/etc/yum.repos.d/pgedge.repo` | New | pgEdge repository configuration on RHEL systems. |
| `/etc/yum.repos.d/epel.repo` | New | EPEL repository configuration on RHEL systems. |

## Platform-Specific Behavior

The role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, the role installs these packages and files:

| Setting | Value |
|---------|-------|
| Prerequisite packages | `curl`, `gnupg2`, `lsb-release` |
| Repository file | `/etc/apt/sources.list.d/pgedge.sources` |
| GPG key location | `/etc/apt/keyrings/pgedge.gpg` |
| Cache update | `apt update` |

### RHEL Family

On RHEL-based systems, the role installs these packages and files:

| Setting | Value |
|---------|-------|
| EPEL installation | Varies by distribution |
| Repository file | `/etc/yum.repos.d/pgedge.repo` |
| GPG key import | Automatic during package installation |
| Cache update | Automatic during repository installation |

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role delegates package installation to the operating system, which
handles existing packages appropriately.
