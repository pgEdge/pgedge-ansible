# Roles Overview

The pgEdge Ansible Collection consists of several specialized roles that work
together to deploy and configure pgEdge Distributed Postgres clusters. This
page provides an overview of all roles, their purposes, and execution order.

## Role Categories

This collection deploys software using a provided Ansible inventory file to 
initialize each inventory host before installing and then configuring the 
software. In order to simplify cluster deployment, each role inhabits one of 
four functional categories described in this section.

### Configuration Foundation

- [role_config](role_config.md) provides shared variables to all other roles.

### Server Preparation

- [init_server](init_server.md) initializes servers with required packages.
- [install_repos](install_repos.md) configures pgEdge package repositories.

### Software Installation

- [install_pgedge](install_pgedge.md) installs Postgres with pgEdge extensions.
- [install_backrest](install_backrest.md) installs the pgBackRest backup tool.
- [install_etcd](install_etcd.md) installs etcd for HA cluster coordination.
- [install_patroni](install_patroni.md) installs Patroni for HA management.

### Service Configuration

- [setup_postgres](setup_postgres.md) initializes and configures Postgres.
- [setup_etcd](setup_etcd.md) configures and starts etcd clusters for HA.
- [setup_patroni](setup_patroni.md) configures and starts Patroni for HA.
- [setup_haproxy](setup_haproxy.md) installs and configures HAProxy for HA.
- [setup_pgedge](setup_pgedge.md) establishes Spock replication between nodes.
- [setup_backrest](setup_backrest.md) configures backups and automation.

## Execution Order

Execute roles in a specific order to ensure proper dependencies. The
recommended execution order differs between simple and HA clusters.

### Simple Cluster Execution Order

In the following example, the playbook deploys a basic multi-node cluster:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server          # 1. Prepare servers
    - install_repos        # 2. Configure repositories
    - install_pgedge       # 3. Install Postgres
    - setup_postgres       # 4. Initialize databases
    - setup_pgedge         # 5. Configure replication
```

In the following example, the playbook adds optional backup configuration:

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

In the following example, the playbook deploys a high-availability cluster:

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
    - install_pgedge       # 3. Install Postgres
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
| [install_pgedge](install_pgedge.md) | Postgres installation | All | ~3-5 min |
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
    Execution times are approximate and vary based on hardware, network speed,
    and cluster size.

## Role Usage Patterns

When working with the pgEdge Ansible Collection, you'll employ roles to 
automate infrastructure provisioning, software installation, and service 
configuration. These roles handle everything from preparing your servers to 
setting up high-availability clusters with replication and load balancing. You 
can include roles in your playbooks in multiple ways: incorporating them 
directly, applying them conditionally based on cluster requirements, or passing 
role-specific variables to customize behavior. The collection provides clear 
patterns for integrating these roles into your deployment workflows, including 
examples for both simple clusters and high-availability configurations. By 
mastering these usage patterns, you'll establish a repeatable, consistent 
process for scaling and maintaining your pgEdge deployments across diverse 
environments.

### Including Roles in Playbooks

Declare roles in a playbook to include them in the execution.

In the following example, the playbook uses the collection declaration to
access all roles from the pgEdge platform collection:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role_name
```

### Conditional Role Execution

Some roles execute only under specific conditions.

In the following example, the playbook uses conditionals to skip HA roles
when the `is_ha_cluster` parameter is `false`:

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

While many roles contain conditionals to control sub-component execution,
playbooks should only execute roles on their intended targets. Omit HA-related
roles for non-HA clusters rather than relying on conditionals. The included
sample playbooks demonstrate this principle.

### Role Variables

Variables determine how Ansible roles operate. Please refer to the
[Configuration](../configuration/index.md) page for a list of all accepted
role variables for this collection.

Some roles accept role-specific parameters.

In the following example, the playbook passes a variable directly to the role:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - role: setup_pgedge
      vars:
        proxy_node: custom-proxy.example.com
```

For cluster consistency, we recommend setting parameters through the inventory 
file when possible.

In the following example, the inventory file sets a variable for all hosts
in the `pgedge` node group:

```yaml
pgedge:
  vars:
    proxy_node: custom-proxy.example.com
```

## Common Role Features

Every role in the pgEdge Ansible Collection implements shared capabilities that 
ensure predictable, reliable automation across all deployment scenarios. These 
features address critical concerns like system state consistency, 
cross-platform compatibility, and operational visibility. By incorporating 
standardized patterns for idempotent operations, operating system detection, 
and comprehensive logging, the roles deliver repeatable deployments while 
minimizing manual intervention.

Whether provisioning a standalone Postgres instance or constructing a 
multi-region high-availability cluster, these capabilities form the foundation 
for robust, maintainable infrastructure automation that adapts seamlessly to 
different environments and requirements.

### Idempotency

All roles in the collection operate idempotently; running them multiple times
produces the same result. However, some roles may encounter issues when you
execute them after a partial failure.

!!! warning "Re-running After Failures"
    The collection is in early development and not fully re-entrant after
    errors. You may need to perform manual cleanup before re-running failed
    playbooks.

### OS Support

All roles support both Debian and RHEL-based distributions, including:

- Debian 12 (Bookworm).
- Rocky Linux 9.

Roles automatically detect the OS family and adjust items such as:

- package names.
- file paths.
- service names.
- configuration locations.

### Logging and Output

Roles provide detailed output during execution:

- Task names clearly indicate current operations.
- Changed or OK status appears for each task.
- Error messages include context for troubleshooting.
- Debug output is available when enabled.

Use the `-v`, `-vv`, or `-vvv` flags for increased verbosity.

In the following example, the command runs a playbook with verbose output:

```bash
ansible-playbook playbook.yml -vv
```

## Next Steps

- Review individual role documentation for detailed information.
- Examine [sample playbooks](../usage.md) for complete examples.
- Understand [configuration variables](../configuration/index.md) for roles.
- Consult the [troubleshooting guide](../troubleshooting/index.md) for
  solutions.
