# pgEdge Distributed Postgres Ansible Collection

Ansible is a common utility for deploying and configuring infrastructure and cluster resources. The pgEdge Ansible collection is a series of roles designed to simplify deployment and management of pgEdge Distributed Postgres clusters.

Each of these will be described here, along with any variables necessary to modify behavior or configuration characteristics.

Full documentation is available in [docs](./docs).

## Installation

These steps will install the `pgedge.platform` collection in your Ansible repository:

```bash
git clone git@github.com:pgEdge/pgedge-ansible.git
cd pgedge-ansible
make install
```

Simply include these two lines in any playbook to invoke any roles from this collection:

```yaml
collections:
- pgedge.platform
```

For example:

```yaml
- hosts: all

  collections:
  - pgedge.platform

  roles:
  - init_server
```

## Quick Start

The easiest way to produce a minimal pgEdge Distributed Postgres cluster is to start with a minimal `inventory.yaml` file containing three hosts, with each host in a separate zone:

```yaml
pgedge:
  vars:
    db_password: secret
  hosts:
    192.168.6.10:
      zone: 1
    192.168.6.11:
      zone: 2
    192.168.6.12:
      zone: 3
```

Then use a simple playbook which calls all of the required roles in the expected order:

```yaml
- hosts: pgedge

  collections:
  - pgedge.platform

  roles:
  - init_server
  - install_repos
  - install_pgedge
  - setup_postgres
  - setup_pgedge
```

This collection should be compatible with inventory files using either IP addresses or hostnames.

## Usage

Files in the [sample-playbooks](./sample-playbooks) directory provide a sample inventory and playbook to illustrate how these roles should be utilized:

* [simple-cluster](./sample-playbooks/simple-cluster) - Produces a standard three-node pgEdge cluster.
* [ultra-ha](./sample-playbooks/ultra-ha) - Produces an Ultra-HA cluster with two zones, three pgEdge nodes in each zone, and one HAProxy node per zone. This is a total of eight nodes.

## Compatibility

This collection has been verified as compatible with the following Linux platforms:

* Debian 12 / Bookworm
* Ubuntu 25.04 / Plucky Puffin
* Rocky Linux 9

They may also work with other Debian or RHEL variants as-is, but this has not been validated.

## Other Notes

This collection is likely to experience heavy revisions as new functionality is introduced. Major version jumps (eg: 0.x to 1.x) will usually include breaking changes to existing playbooks and role parameters. Pay attention to this when updating to avoid unexpected behavior during playbook execution.
