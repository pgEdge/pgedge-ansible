# install_etcd

The `install_etcd` role installs etcd, a distributed key-value store that
Patroni uses for consensus and leader election in high availability Postgres
clusters.

The role performs the following tasks on inventory hosts:

- Install the etcd package from the pgEdge repository.
- Create the etcd system user and data directory.
- Register the etcd systemd service without starting it.

The etcd service is not started by this role. The `setup_etcd` role handles
cluster configuration and service startup.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

Execute this role on pgedge hosts in high availability configurations before
configuring Patroni. Only high availability deployments need this role; set
`is_ha_cluster` to `true` to enable HA mode.

In the following example, the playbook installs etcd as part of a high
availability cluster deployment:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
    - install_patroni
```

## Configuration

This role uses the following parameters from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `etcd_user` | Specify the system user that runs etcd. |
| `etcd_group` | Specify the system group for etcd. |
| `etcd_data_dir` | Set the directory for etcd database storage. |
| `etcd_config_dir` | Set the directory for etcd configuration files. |

See the [Configuration Reference](../configuration.md) for defaults.

## How It Works

The role installs etcd from the pgEdge package repository and prepares the
service for later configuration.

1. Install the etcd package from the pgEdge repository using the system
   package manager (APT or DNF).
2. Create the `etcd_user` system account and the data directory.
3. Register the etcd systemd service unit without starting it.

## Usage Examples

In the following example, the playbook installs etcd using default settings:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_etcd
```

In the following example, the playbook specifies custom paths for etcd:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    etcd_data_dir: /data/etcd
    etcd_config_dir: /opt/etcd/config
  roles:
    - install_etcd
```

## Artifacts

This role creates the following files on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/systemd/system/etcd.service` | New | Systemd service unit for etcd. |
| `{{ etcd_config_dir }}/` | New | Configuration directory for etcd settings. |
| `{{ etcd_data_dir }}/` | New | Data directory for etcd database storage. |

## Platform-Specific Behavior

On Debian-based systems, the role uses APT to install the etcd package. On
RHEL-based systems, the role uses DNF. The etcd binaries are installed to
system paths in both cases.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
skips user creation and package installation when the targets already exist.
