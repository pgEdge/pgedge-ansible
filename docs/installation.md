# Installation

This guide covers the prerequisites and steps required to install the pgEdge Ansible Collection on your Ansible control node.

## Prerequisites

### Ansible Control Node Requirements

The machine where you run Ansible playbooks must meet the following requirements:

- Ansible version 2.12 or later
- Python 3.6 or later
- Git (for cloning the repository)
- Network connectivity to all target hosts
- SSH access to all target hosts

To check your Ansible version:

```bash
ansible --version
```

### Target Host Requirements

Each server in your pgEdge cluster must meet these requirements:

#### Supported Operating Systems

The pgEdge Ansible Collection has been verified on the following operating systems:

- Debian 12 (Bookworm)
- Rocky Linux 9

The collection may also work with other Debian or RHEL variants, but compatibility has not been validated.

#### System Requirements

Each server in your pgEdge cluster must meet the following requirements:

- Architecture: x86_64 (amd64)
- RAM: Minimum 2GB, recommended 4GB or more
- Disk Space: Minimum 20GB available
- Network: All nodes must be able to communicate with each other
- SSH: SSH server running and accessible
- User Access: A user account with sudo/root privileges

#### Network Requirements

Ensure the following ports are accessible between nodes:

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 (default) | Database connections |
| HAProxy | 5432, 5433 (default) | Proxy connections for primary and replica |
| etcd | 2379, 2380 | Distributed key-value store for HA |
| Patroni | 8008 | REST API for health checks |

!!! warning "Firewall Configuration"
    You may need to configure firewall rules to allow traffic between cluster nodes. This collection does not automatically configure firewall rules.

## Installation Methods

### Method 1: Install from Git Repository (Recommended)

This is the current recommended method for installing the collection:

```bash
# Clone the repository
git clone git@github.com:pgEdge/pgedge-ansible.git
cd pgedge-ansible

# Build and install the collection
make install
```

The `make install` command performs the following steps:

1. Read the version from the `VERSION` file
2. Generate a `galaxy.yml` file from the template
3. Build the collection archive
4. Install it to your Ansible collections path

By default, collections are installed to `~/.ansible/collections/ansible_collections/`.

### Method 2: Install from Local Build

If you've already built the collection or received a `.tar.gz` archive:

```bash
# Build the collection without installing
make build

# Install manually
ansible-galaxy collection install pgedge-platform-<version>.tar.gz --force
```

### Method 3: Install from Ansible Galaxy (Future)

!!! note "Coming Soon"
    The collection will eventually be available on Ansible Galaxy for easier installation:
    ```bash
    ansible-galaxy collection install pgedge.platform
    ```
    This functionality is not yet available.

## Verifying Installation

After installation, verify the collection is available:

```bash
ansible-galaxy collection list pgedge.platform
```

You should see output similar to:

```
Collection      Version
--------------- -------
pgedge.platform 1.0.0  
```

## Setting Up Your Environment

### SSH Key Configuration

Ensure you have SSH access to all target hosts:

```bash
# Test SSH access
ssh user@target-host

# If using SSH keys (recommended)
ssh-copy-id user@target-host
```

### Ansible Configuration

Create or update your `ansible.cfg` file to configure behavior:

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

Test connectivity to your hosts before running playbooks:

```bash
# Test all hosts
ansible all -m ping

# Test specific host group
ansible pgedge -m ping
```

## Next Steps

After successful installation:

1. Review the [architecture patterns](architecture.md) to understand cluster design
2. Create an [inventory file](configuration.md#inventory-structure) for your deployment
3. Configure [variables](configuration.md#configuration-variables) for your deployment
4. Examine the [sample playbooks](usage.md#sample-playbooks) for deployment examples
5. Review the [roles documentation](roles/index.md) to understand each component

## Upgrading the Collection

To upgrade to a newer version:

```bash
cd pgedge-ansible
git pull
make install
```

The `--force` flag in the Makefile ensures the new version replaces the existing installation.

## Uninstalling

To remove the collection:

```bash
ansible-galaxy collection remove pgedge.platform
```

To clean up build artifacts in the repository:

```bash
make clean
```

## Troubleshooting

### Collection Not Found

If Ansible cannot find the collection after installation:

1. Check the installation path:
   ```bash
   ansible-galaxy collection list
   ```

2. Verify the collections path in your `ansible.cfg`:
   ```ini
   [defaults]
   collections_paths = ~/.ansible/collections:/usr/share/ansible/collections
   ```

### Build Failures

If `make install` fails:

- Ensure you have `ansible-galaxy` command available
- Check that you have write permissions to the collections directory
- Verify the `VERSION` file exists in the repository root

### SSH Connection Issues

If Ansible cannot connect to hosts:

- Verify SSH access manually: `ssh user@host`
- Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
- Ensure the remote user has appropriate sudo privileges
- Review your inventory file for correct hostnames and connection parameters
