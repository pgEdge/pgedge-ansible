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
  - [Inventory Structure](docs/configuration/inventory.md)
  - [Cluster Configuration](docs/configuration/cluster.md)
  - [Postgres Configuration](docs/configuration/postgres.md)
  - [Proxy Configuration](docs/configuration/proxy.md)
  - [Spock Configuration](docs/configuration/spock.md)
  - [System Configuration](docs/configuration/system.md)
  - [Backup Configuration](docs/configuration/backup.md)
  - [etcd Configuration](docs/configuration/etcd.md)
- Role Reference
  - [Role Overview](docs/roles.md)
  - [role_config](docs/roles/role_config.md)
  - [init_server](docs/roles/init_server.md)
  - [install_repos](docs/roles/install_repos.md)
  - [install_pgedge](docs/roles/install_pgedge.md)
  - [setup_postgres](docs/roles/setup_postgres.md)
  - [install_etcd](docs/roles/install_etcd.md)
  - [install_patroni](docs/roles/install_patroni.md)
  - [install_backrest](docs/roles/install_backrest.md)
  - [setup_etcd](docs/roles/setup_etcd.md)
  - [setup_patroni](docs/roles/setup_patroni.md)
  - [setup_haproxy](docs/roles/setup_haproxy.md)
  - [setup_pgedge](docs/roles/setup_pgedge.md)
  - [setup_backrest](docs/roles/setup_backrest.md)
- Troubleshooting
  - [Troubleshooting Overview](docs/troubleshooting.md)
  - [Installation Issues](docs/troubleshooting/installation.md)
  - [Repository Issues](docs/troubleshooting/repository.md)
  - [System Configuration Issues](docs/troubleshooting/system.md)
  - [PostgreSQL Issues](docs/troubleshooting/postgres.md)
  - [etcd Issues](docs/troubleshooting/etcd.md)
  - [Patroni Issues](docs/troubleshooting/patroni.md)
  - [HAProxy Issues](docs/troubleshooting/haproxy.md)
  - [Spock Replication Issues](docs/troubleshooting/spock.md)
  - [PgBackRest Issues](docs/troubleshooting/backup.md)
- [Changelog](docs/changelog.md)
- [License](docs/LICENSE.md)

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
