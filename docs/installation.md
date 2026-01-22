# Installation

This guide covers the prerequisites and steps required to install the pgEdge
Ansible Collection on your Ansible control node.

## Prerequisites

Before deploying pgEdge with Ansible, ensure your environment meets all 
requirements to guarantee smooth operation. The pgEdge Ansible Collection 
automates complex database provisioning and clustering, but it demands specific 
conditions on both the control node (where you run Ansible) and target hosts 
(where pgEdge components will be deployed).

Meeting these requirements prevents installation failures, connection issues, 
and configuration conflicts during deployment. This section details the exact 
specifications your infrastructure must satisfy—from software versions to 
network configuration—so you can validate your setup before proceeding with 
installation.

### Ansible Control Node Requirements

The machine where you run Ansible playbooks must meet the following
requirements:

- Install Ansible version 2.12 or later on the control node.
- Ensure Python 3.6 or later runs on the system.
- Install Git for cloning the repository.
- Verify the control node has network connectivity to all target hosts.
- Configure SSH access for all target hosts.

The following command checks your Ansible version:

```bash
ansible --version
```

### Target Host Requirements

Each server in your pgEdge cluster must meet these requirements.

#### Supported Operating Systems

The pgEdge team has verified the Ansible Collection on the following operating
systems:

- Debian 12 (Bookworm) receives full support and testing.
- Rocky Linux 9 receives full support and testing.

The collection may work with other Debian or RHEL variants, but the pgEdge
team has not validated compatibility.

#### System Requirements

Each server in your pgEdge cluster must meet the following requirements:

- Use x86_64 (amd64) architecture for all nodes.
- Provide at least 2GB RAM; the pgEdge team recommends 4GB or more.
- Allocate at least 20GB of available disk space.
- Ensure all nodes have network connectivity to communicate with each other.
- Run an SSH server that remains accessible from the control node.
- Provide a user account with sudo or root privileges.

#### Network Requirements

Ensure the following ports are accessible between nodes:

| Service | Port | Purpose |
|---------|------|---------|
| Postgres | 5432 (default) | Database connections |
| HAProxy | 5432, 5433 (default) | Proxy connections for primary and replica |
| etcd | 2379, 2380 | Distributed key-value store for HA |
| Patroni | 8008 | REST API for health checks |

!!! warning "Firewall Configuration"
    You may need to configure firewall rules to allow traffic between cluster
    nodes. This collection does not automatically configure firewall rules.

## Installation Methods

Installing the pgEdge Ansible Collection gives you the tools to automate 
database deployments with confidence and precision. The collection provides a 
wide gamut of installation methods to maximize environment compatibility. This 
includes GitHub source installs, offline deployment with local builds, or 
future inclusion in Ansible Galaxy.

Each method provides the same robust collection of playbooks and roles, 
ensuring consistency regardless of your installation path. This section guides 
you through each option, highlighting best practices and requirements so you 
can integrate pgEdge's automation capabilities seamlessly into your existing 
infrastructure management processes.

### Method 1: Install from Git Repository (Recommended)

This is the current recommended method for installing the collection.

Clone the repository and build the collection:

```bash
git clone git@github.com:pgEdge/pgedge-ansible.git
cd pgedge-ansible
make install
```

The `make install` command performs the following steps:

1. Read the version from the `VERSION` file.
2. Generate a `galaxy.yml` file from the template.
3. Build the collection archive.
4. Install the archive to your Ansible collections path.

By default, Ansible installs collections to the
`~/.ansible/collections/ansible_collections/` directory.

### Method 2: Install from Local Build

Use this method if you have already built the collection or received a
`.tar.gz` archive.

Build and install the collection manually:

```bash
make build
ansible-galaxy collection install pgedge-platform-<version>.tar.gz --force
```

### Method 3: Install from Ansible Galaxy (Future)

!!! note "Coming Soon"
    The collection will eventually be available on Ansible Galaxy for easier
    installation:
    ```bash
    ansible-galaxy collection install pgedge.platform
    ```
    This functionality is not yet available.

## Verifying Installation

After installation, verify Ansible can locate the collection:

```bash
ansible-galaxy collection list pgedge.platform
```

You should see output similar to the following:

```
Collection      Version
--------------- -------
pgedge.platform 1.0.0
```

## Setting Up Your Environment

With the collection installed, your next step is configuring the runtime 
environment to ensure flawless communication between your control node and 
pgEdge infrastructure. Proper environment setup eliminates connection Issues, 
authentication failures, and permission problems that could derail your 
deployment.

This involves establishing secure access methods, optimizing Ansible's behavior 
through configuration, and validating connectivity before executing your first 
playbook. Taking time to configure your environment correctly creates a stable 
foundation for pgEdge's automated provisioning, monitoring, and management 
capabilities.

### SSH Key Configuration

Ensure you have SSH access to all target hosts.

The following commands test SSH access and configure key-based authentication:

```bash
# Test SSH access
ssh user@target-host

# Copy SSH key if using key-based authentication (recommended)
ssh-copy-id user@target-host
```

### Ansible Configuration

Create or update your `ansible.cfg` file to configure behavior.

In the following example, the configuration file sets common options for
cluster deployment:

```ini
[defaults]
# Use the inventory from your project directory
inventory = ./inventory.yaml

# Disable SSH host key checking for new hosts (optional)
host_key_checking = False

# Enable privilege escalation if needed
[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

### Testing Connectivity

Test connectivity to your hosts before running playbooks.

The following commands verify Ansible can reach all hosts:

```bash
# Test all hosts
ansible all -m ping

# Test specific host group
ansible pgedge -m ping
```

## Next Steps

After successful installation:

1. Review [architecture patterns](architecture.md) to understand cluster
   design.
2. Create an [inventory file](configuration/index.md) for your deployment.
3. Configure [variables](configuration/index.md) for your environment.
4. Examine [sample playbooks](usage.md) for deployment examples.
5. Review [roles documentation](roles/index.md) to understand each component.

## Upgrading the Collection

To upgrade to a newer version, pull the latest changes and reinstall:

```bash
cd pgedge-ansible
git pull
make install
```

The `--force` flag in the Makefile ensures the new version replaces the
existing installation.

## Uninstalling

To remove the collection from your Ansible installation:

```bash
ansible-galaxy collection remove pgedge.platform
```

To clean up build artifacts in the repository:

```bash
make clean
```
