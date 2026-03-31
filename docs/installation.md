# Installation

This page describes the prerequisites and installation steps for the
pgEdge Ansible Collection.

## Prerequisites

The following software must be installed on the Ansible controller
before using this collection:

- Ansible 2.12.0 or later.
- Python 3 with the `netaddr` package (required by the
  `ansible.utils.ipaddr` filter).
- SSH access from the Ansible controller to all target nodes.

Each target node must run a supported Linux distribution - Debian 12
(Bookworm) or Rocky 9. The Ansible user on each target node must have
`sudo` privileges.

## Installing the Collection

The collection is not yet published to Ansible Galaxy. To install it
from the
[pgEdge GitHub repository](https://github.com/pgEdge/pgedge-ansible),
run the following commands:

```bash
git clone https://github.com/pgEdge/pgedge-ansible.git
cd pgedge-ansible
make install
```

The `make install` command installs the collection for the current
user. After installation, reference the collection in any playbook
with the following declaration:

```yaml
collections:
  - pgedge.platform
```

## Using the Collection in a Playbook

The following example shows the minimum required structure for a
playbook that uses the pgEdge Ansible Collection:

```yaml
- hosts: all

  collections:
    - pgedge.platform

  roles:
    - init_server
```

Each role in the collection is described in the
[Role Reference](roles.md). Sample playbooks are provided in the
[Simple Cluster](simple_cluster.md) and
[Ultra-HA Cluster](ultra_ha.md) guides.

## Next Steps

- The [Simple Cluster](simple_cluster.md) guide describes deploying
  a basic three-node pgEdge Distributed Postgres cluster.
- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
