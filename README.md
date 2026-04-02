# pgEdge Ansible Collection

## Table of Contents

- [Overview](docs/index.md)
- [Architecture](docs/architecture.md)
- Installing with Ansible
  - [Installation Overview](docs/installation.md)
  - [Tutorial - Deploying a Simple Cluster](docs/simple_cluster.md)
  - [Tutorial - Deploying an Ultra-HA Cluster](docs/ultra_ha.md)
  - [Customizing a Playbook for One or More Zones](docs/configure_playbook.md)
- [Using the pgEdge Ansible Collection](docs/usage.md)
- Configuration Reference
  - [Configuration Overview](docs/configuration.md)
- Role Reference
  - [Role Overview](docs/roles.md)
- Troubleshooting
  - [Troubleshooting Overview](docs/troubleshooting.md)
- [Changelog](docs/changelog.md)
- [License](docs/LICENSE.md)

The pgEdge Ansible Collection provides a set of Ansible roles for deploying
and configuring pgEdge Distributed Postgres clusters. The collection automates
cluster provisioning from initial server preparation through PostgreSQL
initialization, High Availability configuration, and backup setup.

> **Note:** Version 1.x introduces breaking changes from the 0.x release
> series. Inventory structure, role parameters, and installation behavior
> have changed significantly. Review the [Changelog](docs/changelog.md)
> and [Installation Overview](docs/installation.md) before upgrading.

## Compatibility

The collection has been verified as compatible with the following Linux
platforms:

- Debian 12 / Bookworm
- Ubuntu 25.04 / Plucky Puffin
- Rocky Linux 9

The collection may also work with other Debian or RHEL variants, but the
pgEdge team has not validated compatibility.

## Installation

Ansible 2.12.0 or later and Python 3 with the `netaddr` package are required
on the Ansible controller. Target nodes must have `sudo` privileges.

Install the collection from the
[pgEdge GitHub repository](https://github.com/pgEdge/pgedge-ansible)
by running the following commands:

```bash
git clone https://github.com/pgEdge/pgedge-ansible.git
cd pgedge-ansible
make install
```

After installation, reference the collection in any playbook with the
following declaration:

```yaml
collections:
  - pgedge.platform
```

## Quick Start

The following example shows the minimum inventory and playbook required to
deploy a three-node pgEdge Distributed Postgres cluster. Each host must be
in a separate zone:

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

The following playbook applies all roles required for a simple cluster:

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

See the [Simple Cluster](docs/simple_cluster.md) and
[Ultra-HA Cluster](docs/ultra_ha.md) tutorials for complete deployment
walkthroughs.

## Configuration

All roles recognize a common set of parameters set as inventory or playbook
variables. The following table lists the most commonly used parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| cluster_name | demo | Canonical name for the cluster. |
| zone | 1 | Zone or region for a node; also the Snowflake node ID. |
| pg_version | 17 | PostgreSQL version to install. |
| db_names | [demo] | List of databases to create. |
| db_user | admin | Database superuser username. |
| db_password | secret | Password for db_user. |
| is_ha_cluster | false | When true, installs etcd, Patroni, and HAProxy. |

For the complete parameter list, see the
[Configuration Reference](docs/configuration.md).

## Using pgEdge Ansible Collection

Sample playbooks are provided in the
[sample-playbooks](./sample-playbooks) directory:

- [simple-cluster](./sample-playbooks/simple-cluster) - Deploys a standard
  three-node pgEdge Distributed Postgres cluster.
- [ultra-ha](./sample-playbooks/ultra-ha) - Deploys a two-zone Ultra-HA
  cluster with Patroni, etcd, HAProxy, and PgBackRest.

Run a playbook with the following command, substituting your inventory file
path:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

## Documentation

Full documentation is available at [docs.pgedge.com](https://docs.pgedge.com).
To build documentation from source, install MkDocs Material and run:

```bash
pip install mkdocs-material
mkdocs serve
```

## Support & Resources

For more information, visit [docs.pgedge.com](https://docs.pgedge.com).

To report an issue with the software, visit:
[https://github.com/pgEdge/pgedge-ansible/issues](https://github.com/pgEdge/pgedge-ansible/issues)

## License

This project is licensed under the [PostgreSQL License](LICENSE.md).
