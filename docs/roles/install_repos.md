# install_repos

## Overview

The `install_repos` role configures official pgEdge package repositories on target systems, enabling installation of pgEdge Enterprise PostgreSQL packages and dependencies. This includes adding EPEL (Extra Packages for Enterprise Linux) on RHEL-based systems to satisfy certain dependencies.

## Purpose

The role performs the following tasks:

- installs prerequisite packages for repository management.
- adds pgEdge package repositories for the target OS.
- configures the EPEL repository on RHEL-based systems.
- imports and verifies GPG keys for package signing.
- updates the package cache to make pgEdge packages available.

## Role Dependencies

- `role_config`: Provides shared configuration variables
- `init_server`: Systems should be prepared prior to installing repositories

## When to Use

Execute this role on **all hosts** where you will install pgEdge PostgreSQL packages. You should run this role before any package installation roles:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Parameters

This role uses no custom parameters. The role handles all repository configuration automatically based on the detected operating system.

## Tasks Performed

### 1. Repository Setup

#### Debian-Family Systems

**Prerequisite Package Installation:**

- `curl` - For downloading repository packages
- `gnupg2` - For GPG key verification
- `lsb-release` - For OS version detection

**pgEdge Repository Configuration:**

- Downloads and installs the pgEdge repository definition package.
- Updates the APT package cache to include pgEdge packages.
- Configures automatic repository sources in `/etc/apt/sources.list.d/`.

#### RHEL-Family Systems

**EPEL Repository Installation:**

The role detects the specific RHEL variant and installs EPEL accordingly:

- **RHEL 8, 9**: Enables EPEL via DNF configuration manager
- **RHEL 10**: Enables EPEL via subscription manager
- **Rocky or AlmaLinux 8+**: Installs EPEL from existing repos
- **Oracle Linux 8+**: Installs Fedora EPEL package

**pgEdge Repository Installation:**

- Imports the pgEdge GPG key.
- Downloads and installs the pgEdge repository definition package.
- Configures the YUM/DNF repository in `/etc/yum.repos.d/`.

### 2. Package Cache Update

After repository installation:

- **Debian**: Runs `apt update`
- **RHEL**: DNF automatically updates metadata during repository installation

## Files Generated

### On Debian/Ubuntu Systems

- `/etc/apt/sources.list.d/pgedge.sources` - pgEdge repository configuration
- `/etc/apt/keyrings/pgedge.gpg` - Public pgEdge GPG key

### On RHEL-based Systems

- `/etc/yum.repos.d/pgedge.repo` - pgEdge repository configuration
- `/etc/yum.repos.d/epel.repo` - EPEL repository configuration

## Example Usage

### Basic Repository Installation

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

### Multi-Group Installation

```yaml
# Install repos on all PostgreSQL nodes
- hosts: pgedge
  roles:
    - install_repos

# Install repos on backup servers
- hosts: backup
  roles:
    - install_repos
```

## Idempotency

This role is idempotent and safe to re-run. Subsequent executions will:

- delegate package installation to the operating system.

## Notes

!!! important "Execution Order"
    You must execute this role before any `install_*` roles that install pgEdge packages. The role establishes the package sources needed for all subsequent installations.

!!! warning "EPEL Dependencies"
    EPEL is required on RHEL-based systems for several PostgreSQL dependencies. The role handles EPEL installation automatically but may require subscription access on RHEL systems.

!!! note "Network Requirements"
    This role requires outbound HTTPS access to pgEdge repository servers. Ensure firewall rules and proxy settings allow this connectivity.
