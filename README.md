# pgEdge Ansible Collection

## Table of Contents

- [Getting Started](docs/installation.md)
- [Deploying a Cluster](docs/simple_cluster.md)
  - [Simple Cluster](docs/simple_cluster.md)
  - [Ultra-HA Cluster](docs/ultra_ha.md)
- [Configuration Reference](docs/configuration.md)
- [Role Reference](docs/roles.md)
- [Release Notes](docs/changelog.md)

The pgEdge Ansible Collection provides a set of Ansible roles for deploying
and configuring pgEdge Distributed Postgres clusters. The collection automates
cluster provisioning from initial server preparation through PostgreSQL
initialization, High Availability configuration, and backup setup.

## Installation

Ansible 2.12.0 or later and Python 3 with the `netaddr` package are required
on the Ansible controller. Target nodes must run Debian 12 (Bookworm) or Rocky
9 and the Ansible user must have `sudo` privileges.

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
