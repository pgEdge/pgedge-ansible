# install_patroni

The `install_patroni` role installs Patroni, a high availability solution for
Postgres that uses etcd for distributed consensus. Patroni manages automatic
failover, leader election, and cluster configuration.

The role performs the following tasks on inventory hosts:

- Install OS-specific prerequisite packages for Debian or RHEL.
- Install the Patroni package from the pgEdge repository.
- Create the Patroni configuration directory at `/etc/patroni`.
- Register the Patroni systemd service without starting it.

The Patroni service is not started by this role. The `setup_patroni` role
handles cluster configuration and service startup.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` creates the postgres OS user that the installation needs.
- `install_pgedge` installs Postgres before Patroni can manage the cluster.

## When to Use

Execute this role on pgedge hosts in high availability configurations after
installing Postgres and etcd. Only high availability deployments need this
role; set `is_ha_cluster` to `true` to enable HA mode.

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

## Configuration

This role uses the following parameter from the inventory file:

| Parameter | Use Case |
|-----------|----------|
| `patroni_tls_dir` | Set the directory for Patroni TLS certificate files. |

## How It Works

The role installs Patroni from the pgEdge package repository and prepares the
configuration directory.

1. Install OS-specific prerequisite packages using APT (Debian) or DNF
   (RHEL).
2. Install the Patroni package from the pgEdge repository.
3. Create the configuration directory at `/etc/patroni` and the TLS directory
   at `patroni_tls_dir` with `postgres:postgres` ownership and mode 0700.

## Usage Examples

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

## Artifacts

This role creates the following directories on inventory hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/patroni/` | New | Patroni configuration directory. |
| `{{ patroni_tls_dir }}/` | New | TLS certificate directory; populated by `setup_patroni`. |

## Platform-Specific Behavior

On Debian-based systems, this role uses APT and installs distribution-specific
prerequisite packages before the Patroni package. On RHEL-based systems, this
role uses DNF with its own set of prerequisites.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. Package
installation is skipped when packages are already present.
