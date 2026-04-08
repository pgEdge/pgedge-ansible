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

Execute this role on all hosts where you will install pgEdge packages. Run
this role before any package installation roles. The `repo_name` parameter
controls which repository tier to use: `release`, `staging`, or `daily`.

In the following example, the playbook configures repositories on all pgedge
hosts:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Configuration

This role uses no custom parameters beyond the shared `repo_name` parameter.
The role handles all repository configuration automatically based on the
detected operating system.

## How It Works

The role configures package repositories based on the operating system family
detected on each target host.

### Debian Family Setup

On Debian-based systems, the role performs the following steps:

1. Install prerequisite packages including `curl`, `gnupg2`, and
   `lsb-release`.
2. Download and install the pgEdge repository definition package.
3. Update the APT package cache to include pgEdge packages.

### RHEL Family Setup

On RHEL-based systems, the role performs the following steps:

1. Install the EPEL repository using the appropriate method for the
   distribution variant.
2. Import the pgEdge GPG key for package verification.
3. Download and install the pgEdge repository definition package.

!!! important "Execution Order"
    Execute this role before any `install_*` roles that install pgEdge
    packages. The role establishes the package sources that all subsequent
    installations need.

!!! warning "EPEL Dependencies"
    RHEL-based systems require EPEL for several Postgres dependencies. The
    role handles EPEL installation automatically but may require subscription
    access on RHEL systems.

!!! note "Network Requirements"
    This role requires outbound HTTPS access to pgEdge repository servers.
    Ensure firewall rules and proxy settings allow this connectivity.

## Usage Examples

In the following example, the playbook configures pgEdge repositories on
pgedge hosts and backup servers:

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

This role creates the following repository configuration files on inventory
hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/apt/sources.list.d/pgedge.sources` | New | pgEdge repository configuration on Debian systems. |
| `/etc/apt/keyrings/pgedge.gpg` | New | pgEdge GPG key on Debian systems. |
| `/etc/yum.repos.d/pgedge.repo` | New | pgEdge repository configuration on RHEL systems. |
| `/etc/yum.repos.d/epel.repo` | New | EPEL repository configuration on RHEL systems. |

## Platform-Specific Behavior

On Debian-based systems, the role installs `curl`, `gnupg2`, and `lsb-release`
as prerequisites and uses APT to manage the package cache. On RHEL-based
systems, the EPEL installation method varies by distribution variant and
the role uses DNF for all package operations.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
delegates package installation to the operating system, which handles existing
packages appropriately.
