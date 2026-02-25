# install_patroni

The `install_patroni` role installs Patroni, a high availability solution for
Postgres that uses etcd for distributed consensus. Patroni manages automatic
failover, leader election, and cluster configuration.

The role performs the following tasks on inventory hosts:

- Install Patroni from the Postgres package repository.
- Create the Patroni TLS configuration directory.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` creates the postgres user that the installation process needs.
- `install_pgedge` installs Postgres before Patroni can manage the cluster.

## When to Use

Execute this role on pgedge hosts in high availability configurations after
installing Postgres and etcd.

In the following example, the playbook installs Patroni as part of a high
availability cluster deployment:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_pgedge
    - install_etcd
    - install_patroni
```

!!! important "HA Clusters Only"
    Only high availability deployments need Patroni; set the `is_ha_cluster`
    parameter to `true` to enable HA mode. Standalone Postgres instances do
    not need Patroni.

## Configuration

This role utilizes several of the collection-wide configuration parameters
described in the [Configuration section](../configuration/index.md).

Set the parameters in the inventory file as shown in the following example:

```yaml
pgedge:
  vars:
    patroni_tls_dir: /etc/ssl/patroni
```

Below is a complete list of valid parameters that affect the operation of
this role:

| Option | Use Case |
|--------|----------|
| `patroni_tls_dir` | Set the directory for Patroni TLS certificate files. |

## How It Works

The role installs Patroni using pipx to create an isolated Python environment
that prevents conflicts with system packages.

1. Install Patroni from the Postgres package repository.
    - Use distribution-specific management (apt/dnf) to install package.
2. Create the TLS certificate configuration directory.
    - Create the `patroni_tls_dir` directory for YAML configuration.
    - Set ownership to `postgres:postgres` for proper access.
    - Apply secure permissions with mode 0700.

## Usage Examples

Here are a few examples of how to use this role in an Ansible playbook.

### Basic Usage

In the following example, the playbook installs Patroni for a high
availability cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_pgedge
    - install_etcd
    - install_patroni
```

### Custom TLS Directory

In the following example, the playbook specifies a custom directory for
Patroni TLS certificates:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    patroni_tls_dir: "/etc/ssl/patroni"
  roles:
    - install_patroni
```

## Artifacts

This role generates and modifies files on inventory hosts during execution.

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `{{ patroni_tls_dir }}/` | New | TLS configuration directory; populated by `setup_patroni`. |

## Platform-Specific Behavior

This role adapts its behavior based on the operating system family.

### Debian Family

On Debian-based systems, this role performs these actions:

- Uses the `apt` package manager for package installation.

### RHEL Family

On RHEL-based systems, this role performs these actions:

- Uses the `dnf` package manager for package installation.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts.

The role skips these operations when the target already exists:

- Package installation when packages are already present.
