# Installation

This page describes the prerequisites and installation steps for the pgEdge
Ansible Collection.

## Prerequisites

The following software must be installed on the Ansible controller before
using this collection:

- Ansible 2.12.0 or later.
- Python 3 with the `netaddr` package (required by the
  `ansible.utils.ipaddr` filter).
- Git for cloning the repository.
- SSH access from the Ansible controller to all target nodes.

Each target node must run Debian 12 (Bookworm) or Rocky Linux 9. The
collection may work with other Debian or RHEL variants, but the pgEdge team
has not validated compatibility. The Ansible user on each target node must
have `sudo` privileges.

## Network Requirements

Ensure the following ports are accessible between cluster nodes:

| Service | Port | Purpose |
|---------|------|---------|
| Postgres | 5432 (default) | Database connections |
| HAProxy | 5432, 5433 (default) | Primary and replica proxy connections |
| etcd | 2379, 2380 | Distributed coordination for HA |
| Patroni | 8008 | REST API for health checks |

The collection does not configure firewall rules. You must open these ports
in your firewall before running the playbook.

## Installing the Collection

The collection is not yet published to Ansible Galaxy. To install it from the
[pgEdge GitHub repository](https://github.com/pgEdge/pgedge-ansible), run the
following commands:

```bash
git clone https://github.com/pgEdge/pgedge-ansible.git
cd pgedge-ansible
make install
```

The `make install` command reads the version from the `VERSION` file, builds
a collection archive, and installs it for the current user. By default,
Ansible installs collections to `~/.ansible/collections/ansible_collections/`.

After installation, verify that Ansible can locate the collection:

```bash
ansible-galaxy collection list pgedge.platform
```

## Using the Collection in a Playbook

Reference the collection in any playbook with the following declaration:

```yaml
collections:
  - pgedge.platform
```

The following example shows the minimum required structure for a playbook
that uses the collection:

```yaml
- hosts: all

  collections:
    - pgedge.platform

  roles:
    - init_server
```

## Configuring the Ansible Controller

The following example `ansible.cfg` configures common options for cluster
deployment:

```ini
[defaults]
inventory = ./inventory.yaml
host_key_checking = False

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

Test connectivity to your hosts before running playbooks:

```bash
ansible all -m ping
```

## Upgrading the Collection

To upgrade to a newer version, pull the latest changes and reinstall:

```bash
cd pgedge-ansible
git pull
make install
```

## Next Steps

- The [Architecture](architecture.md) page describes supported cluster
  topologies and design considerations.
- The [Simple Cluster](simple_cluster.md) guide walks through a basic
  three-node deployment.
- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
