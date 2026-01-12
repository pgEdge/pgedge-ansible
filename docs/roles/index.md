# Roles Overview

The pgEdge Ansible Collection consists of several specialized roles that work together to deploy and configure pgEdge Distributed Postgres clusters. This page provides an overview of all roles, their purposes, and intended execution order.

## Role Categories

The roles are organized into four functional categories:

### Configuration Foundation

- [role_config](role_config.md): Central configuration role providing shared variables

### Server Preparation

- [init_server](init_server.md): Initializes servers with required packages and configuration
- [install_repos](install_repos.md): Configures pgEdge package repositories

### Software Installation

- [install_pgedge](install_pgedge.md): Installs PostgreSQL with pgEdge enhancements
- [install_backrest](install_backrest.md): Installs pgBackRest backup software
- [install_etcd](install_etcd.md): Installs etcd distributed key-value store (HA only)
- [install_patroni](install_patroni.md): Installs Patroni HA management system (HA only)

### Service Configuration

- [setup_postgres](setup_postgres.md): Initializes and configures PostgreSQL instances
- [setup_etcd](setup_etcd.md): Configures and starts etcd clusters (HA only)
- [setup_patroni](setup_patroni.md): Configures and starts Patroni (HA only)
- [setup_haproxy](setup_haproxy.md): Installs and configures HAProxy load balancers (HA only)
- [setup_pgedge](setup_pgedge.md): Establishes Spock replication between nodes
- [setup_backrest](setup_backrest.md): Configures backups and automation

## Execution Order

You must execute roles in a specific order to ensure proper dependencies. The recommended execution order differs between simple and HA clusters.

### Simple Cluster Execution Order

For a basic multi-node cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server          # 1. Prepare servers
    - install_repos        # 2. Configure repositories
    - install_pgedge       # 3. Install PostgreSQL
    - setup_postgres       # 4. Initialize databases
    - setup_pgedge         # 5. Configure replication
```

Optional backup configuration:

```yaml
# For pgEdge nodes with backups
- hosts: pgedge
  roles:
    - install_backrest     # After setup_postgres
    - setup_backrest       # After setup_pgedge

# For dedicated backup servers
- hosts: backup
  roles:
    - install_repos
    - install_backrest
    - setup_backrest
```

### HA Cluster Execution Order

For high-availability clusters:

```yaml
# Initialize all hosts
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server          # 1. Prepare all servers

# Configure pgEdge nodes
- hosts: pgedge
  roles:
    - install_repos        # 2. Configure repositories
    - install_pgedge       # 3. Install PostgreSQL
    - setup_postgres       # 4. Initialize databases
    - install_etcd         # 5. Install etcd
    - install_patroni      # 6. Install Patroni
    - install_backrest     # 7. Install backup software (optional)
    - setup_etcd           # 8. Configure etcd clusters
    - setup_patroni        # 9. Configure Patroni
    - setup_backrest       # 10. Configure backups (optional)

# Configure HAProxy nodes
- hosts: haproxy
  roles:
    - setup_haproxy        # 11. Set up load balancers

# Establish replication
- hosts: pgedge
  roles:
    - setup_pgedge         # 12. Configure Spock replication

# Configure backup servers
- hosts: backup
  roles:
    - install_repos
    - install_backrest
    - setup_backrest       # 13. Final backup configuration
```

## Role Quick Reference

| Role | Purpose | Required For | Execution Time |
|------|---------|--------------|----------------|
| [role_config](role_config.md) | Shared configuration | All | N/A (included) |
| [init_server](init_server.md) | Server initialization | All | ~2-5 min |
| [install_repos](install_repos.md) | Repository setup | All | ~1-2 min |
| [install_pgedge](install_pgedge.md) | PostgreSQL installation | All | ~3-5 min |
| [install_etcd](install_etcd.md) | etcd installation | HA clusters | ~1-2 min |
| [install_patroni](install_patroni.md) | Patroni installation | HA clusters | ~2-3 min |
| [install_backrest](install_backrest.md) | Backup software | Optional | ~1 min |
| [setup_postgres](setup_postgres.md) | Database initialization | All | ~2-5 min |
| [setup_etcd](setup_etcd.md) | etcd configuration | HA clusters | ~1-2 min |
| [setup_patroni](setup_patroni.md) | Patroni configuration | HA clusters | ~3-5 min |
| [setup_haproxy](setup_haproxy.md) | Load balancer setup | HA clusters | ~1 min |
| [setup_pgedge](setup_pgedge.md) | Replication setup | All | ~2-5 min |
| [setup_backrest](setup_backrest.md) | Backup configuration | Optional | ~5-10 min |

!!! note "Timing Estimates"
    Execution times are approximate and vary based on hardware, network speed, and cluster size.

## Role Usage Patterns

### Including Roles in Playbooks

Roles are used by declaring them in a playbook:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role_name
```

The `collections` declaration makes all roles from the pgEdge platform collection available.

### Conditional Role Execution

Some roles should only execute under specific conditions:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    - install_pgedge
    - role: install_etcd
      when: is_ha_cluster | default(false) | bool
    - role: install_patroni
      when: is_ha_cluster | default(false) | bool
```

While many roles contain conditionals to control execution of sub-components, playbooks should only execute roles on their intended targets. You can build playbooks more easily by omitting HA-related roles for non-HA clusters rather than enforcing conditionals. The included sample playbooks demonstrate this principle.

### Role Variables

Most configuration is handled through inventory variables. See the [Configuration](../configuration.md) page for details.

Some roles accept role-specific parameters:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role: setup_pgedge
      vars:
        proxy_node: custom-proxy.example.com
```

However, for the sake of cluster consistency, we recommend setting these across the cluster through the inventory file when possible:

```yaml
pgedge:
  vars:
    proxy_node: custom-proxy.example.com
```

## Common Role Features

### Idempotency

The collection designs all roles to be idempotent - running them multiple times produces the same result. However, some roles (particularly setup roles) may encounter issues if you run them after a partial failure.

!!! warning "Re-running After Failures"
    The collection is in early development and not fully re-entrant after errors. Manual cleanup may be required before re-running failed playbooks.

### OS Support

All roles support both Debian and RHEL-based distributions:

- Debian 12 (Bookworm)
- Rocky Linux 9

Roles automatically detect the OS family and adjust:

- Package names
- File paths
- Service names
- Configuration locations

### Logging and Output

Roles provide detailed output during execution:

- Task names clearly indicate current operations
- Changed/OK status for each task
- Error messages with context
- Debug output when available

Use `-v`, `-vv`, or `-vvv` flags for increased verbosity:

```bash
ansible-playbook playbook.yml -vv
```

## Troubleshooting Roles

### Check Mode

Test role execution without making changes:

```bash
ansible-playbook playbook.yml --check
```

!!! note "Check Mode Limitations"
    Some tasks may fail in check mode if they depend on changes from previous tasks.

### Debugging Individual Roles

Run a specific role in isolation:

```bash
ansible-playbook playbook.yml --tags role_name
```

### Common Issues

**Package installation failures:**

- Check internet connectivity
- Verify repository configuration

**Service start failures:**

- Check service logs: `journalctl -u service-name`
- Verify port availability
- Review configuration files

**Role dependencies not met:**

- Ensure roles execute in proper order
- Verify prerequisite roles completed successfully

## Next Steps

- Review individual role documentation for detailed information.
- Examine [sample playbooks](../usage.md) for complete examples.
- Understand [configuration variables](../configuration.md) that affect role behavior.
- Review individual role documentation for detailed information
- Examine [sample playbooks](../usage.md) for complete examples
- Understand [configuration variables](../configuration.md) that affect role behavior
