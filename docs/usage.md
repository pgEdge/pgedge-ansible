# Usage Examples

This page provides practical examples for deploying pgEdge clusters using the
Ansible collection; examples range from simple configurations to complex
high-availability setups.

## Before You Begin

Ensure you have completed the following steps:

1. Install the collection as described in the 
   [installation guide](installation.md).
2. Review the [architecture patterns](architecture.md) for deployment options.
3. Understand [configuration variables](configuration/index.md) for 
   customization.
4. Prepare target hosts with SSH access and appropriate permissions.

!!! important "Multi-Stage Playbooks"
    Cluster designs that require multiple node types restrict certain roles to
    specific node groups. Sample playbooks include the following play at the
    top:

    ```yaml
    - hosts: all
      collections:
      - pgedge.platform
      roles:
      - init_server
    ```

    This ensures Ansible populates host variables for every server in the
    inventory. Some roles require variables for hosts outside the intended
    role group. For example, a `pgedge` node may need information about nodes
    in the `backup` group. If you prefer not to invoke `init_server` at the
    top of every playbook, use a dummy play like this instead:

    ```yaml
    - hosts: all
      roles: []
    ```

## Sample Playbooks

The repository includes sample playbooks in the `sample-playbooks/` directory:

- The `simple-cluster` directory contains a standard three-node cluster.
- The `ultra-ha` directory contains an Ultra-HA cluster with multiple zones.

These samples serve as templates for your own deployments.

## Simple Three-Node Cluster

The simplest deployment consists of three pgEdge nodes with direct replication
between them.

### Inventory File

In the following example, the inventory file defines a three-node cluster with
one node per zone:

```yaml
# Simple three-node cluster with one node per zone
pgedge:
  vars:
    cluster_name: demo
    pg_version: 17
    db_password: changeme123
    db_names:
      - myapp
  hosts:
    node1.example.com:
      zone: 1
    node2.example.com:
      zone: 2
    node3.example.com:
      zone: 3
```

### Playbook File

In the following example, the playbook deploys a basic cluster with Spock
replication:

```yaml
---
- hosts: pgedge
  collections:
    - pgedge.platform

  roles:
    - init_server         # Prepare servers
    - install_repos       # Configure repositories
    - install_pgedge      # Install Postgres
    - setup_postgres      # Initialize database
    - setup_pgedge        # Configure multi-master replication
```

### Running the Playbook

In the following example, the `ansible-playbook` command executes the playbook
against the inventory:

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

### What Gets Deployed

This configuration creates the following components:

- Postgres 17 runs on each node with required extensions.
- Spock extension provides multi-master replication between nodes.
- Full-mesh replication synchronizes data across all three nodes.
- The setup creates a database named `myapp` on all nodes.

### Connecting to the Cluster

In the following example, the `psql` command connects to the cluster:

```bash
psql -h node1.example.com -U admin myapp
```

Spock replicates data written to any node to all other nodes automatically.

## High-Availability Single-Zone Cluster

Deploy a single-zone HA cluster with automatic failover using Patroni and etcd.

### Inventory File

In the following example, the inventory file defines an HA cluster with all
nodes in a single zone:

```yaml
pgedge:
  vars:
    cluster_name: demo
    is_ha_cluster: true     # Enable HA features
    db_password: secure_password
    synchronous_mode: true  # Enable synchronous replication
    zone: 1                 # All nodes in same zone form Patroni cluster
  hosts:
    pg-node1.example.com:
    pg-node2.example.com:
    pg-node3.example.com:

haproxy:
  hosts:
    proxy1.example.com:
      zone: 1
```

### Playbook File

In the following example, the playbook deploys an HA cluster with HAProxy:

```yaml
---
# Initialize all hosts
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server

# Configure pgEdge nodes with HA components
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
    - install_etcd
    - install_patroni
    - setup_etcd
    - setup_patroni

# Configure HAProxy
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy

# Establish pgEdge replication
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_pgedge
```

### What Gets Deployed

This configuration creates the following components:

- Patroni manages the Postgres cluster in zone 1.
- An etcd cluster provides distributed consensus.
- HAProxy routes connections to the current primary node.
- Automatic failover activates when the primary becomes unavailable.

### Testing Failover

In the following example, commands verify and test the HA cluster:

```bash
# Connect through HAProxy
psql -h proxy1.example.com -U admin -d demo

# Check cluster status
sudo su - postgres
patronictl -c /etc/patroni/patroni.yaml list

# Trigger failover
sudo su - postgres
patronictl -c /etc/patroni/patroni.yaml failover
```

## Ultra-HA Multi-Zone Cluster

The most robust configuration provides HA within zones and replication between
zones.

### Inventory File

In the following example, the inventory file defines a multi-zone Ultra-HA
cluster:

```yaml
pgedge:
  vars:
    cluster_name: ultra-ha-cluster
    is_ha_cluster: true
    db_password: "{{ vault_db_password }}"
    pgedge_password: "{{ vault_pgedge_password }}"
    synchronous_mode: true
    db_names:
      - myapp

  hosts:
    # Zone 1 - Three nodes
    pg-z1-n1.example.com:
      zone: 1
    pg-z1-n2.example.com:
      zone: 1
    pg-z1-n3.example.com:
      zone: 1

    # Zone 2 - Three nodes
    pg-z2-n1.example.com:
      zone: 2
    pg-z2-n2.example.com:
      zone: 2
    pg-z2-n3.example.com:
      zone: 2

haproxy:
  hosts:
    proxy-z1.example.com:
      zone: 1
    proxy-z2.example.com:
      zone: 2

backup:
  hosts:
    backup-z1.example.com:
      zone: 1
    backup-z2.example.com:
      zone: 2
```

### Playbook File

In the following example, the playbook deploys a complete Ultra-HA cluster:

```yaml
---
# Initialize all hosts
- hosts: all
  any_errors_fatal: true
  collections:
    - pgedge.platform
  roles:
    - init_server

# Deploy pgEdge nodes with full stack
- hosts: pgedge
  any_errors_fatal: true
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_pgedge
    - setup_postgres
    - install_etcd
    - install_patroni
    - install_backrest
    - setup_etcd
    - setup_patroni
    - setup_backrest

# Configure HAProxy nodes
- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy

# Establish inter-zone replication
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_pgedge

# Configure backup servers
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
    - setup_backrest
```

### What Gets Deployed

This configuration creates the following components:

- Two Patroni clusters operate independently in separate zones.
- An etcd cluster runs in each zone for local consensus.
- HAProxy in each zone routes traffic to local primary nodes.
- Spock replication synchronizes data between zones through HAProxy.
- Automated backups run on dedicated backup servers.
- Full redundancy exists at all levels for maximum availability.

### Connection Architecture

Applications connect through HAProxy to reach their local Patroni cluster:

```
Application (Zone 1) -> proxy-z1 -> Patroni Cluster Zone 1 -> Spock -> Zone 2
Application (Zone 2) -> proxy-z2 -> Patroni Cluster Zone 2 -> Spock -> Zone 1
```

## Adding Backups to Existing Cluster

Add backup capability to an already-deployed cluster using S3 or SSH methods.

### S3 Backups

In the following example, the inventory configures S3-based backups:

```yaml
pgedge:
  vars:
    backup_repo_type: s3
    backup_repo_path: /pgbackrest
    backup_repo_params:
      region: us-west-2
      endpoint: s3.amazonaws.com
      bucket: my-pg-backups
      access_key: "{{ vault_aws_access_key }}"
      secret_key: "{{ vault_aws_secret_key }}"
    full_backup_schedule: "0 2 * * 0"    # Sunday 2 AM
    diff_backup_schedule: "0 2 * * 1-6"  # Mon-Sat 2 AM
```

In the following example, the playbook configures backup on existing nodes:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_backrest
    - setup_backrest
```

### SSH Backups with Dedicated Server

Add backup hosts to your inventory:

```yaml
backup:
  hosts:
    backup-server.example.com:
      zone: 1
```

Update the pgedge group in your inventory:

```yaml
pgedge:
  vars:
    backup_repo_type: ssh
```

In the following example, the playbook configures backup on all relevant hosts:

```yaml
# Populate all server variables
- hosts: all
  roles: [ ]

# Set up pgEdge nodes for backup
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_backrest
    - setup_backrest

# Configure backup server
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
    - install_backrest
    - setup_backrest
```

## Customization Examples

The pgEdge Ansible collection provides extensive flexibility for tailoring 
deployments to specific requirements. These examples demonstrate how to modify 
core parameters such as Postgres version, database configuration, network 
settings, and replication behavior. Whether adjusting for compliance needs, 
performance optimization, or integration with existing infrastructure, the 
collection's modular design allows precise control over deployment aspects. 
Each customization builds upon the foundation established in earlier examples, 
showing how to extend base configurations while maintaining the integrity of 
replication, high availability, and backup mechanisms.

### Custom Postgres Version

In the following example, the inventory specifies a different Postgres
version:

```yaml
pgedge:
  vars:
    pg_version: 18
```

### Custom Database Configuration

In the following example, the inventory creates multiple databases with custom
users:

```yaml
pgedge:
  vars:
    db_names:
      - production
      - staging
      - reporting
    db_user: appuser
    db_password: "{{ vault_db_password }}"
    pgedge_user: replication
    pgedge_password: "{{ vault_repl_password }}"
```

### Custom Ports

In the following example, the inventory configures HAProxy on the standard
Postgres port while moving Postgres to another port:

```yaml
pgedge:
  vars:
    pg_port: 5433
    proxy_port: 5432  # HAProxy listens on standard port
```

### Strict Synchronous Replication

In the following example, the inventory enables strict synchronous replication
that prevents writes when replicas become unavailable:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    synchronous_mode_strict: true  # Prevents writes if replicas unavailable
```

## Testing Your Deployment

Ensuring deployment health requires systematic verification of all cluster 
components. This section provides essential checks for Postgres instances, 
replication status, HA infrastructure, and backup systems. Regular testing 
identifies configuration issues early and confirms that critical failover 
mechanisms operate correctly. These verification techniques apply to simple 
clusters, HA configurations, and Ultra-HA deployments, offering targeted 
commands for each scenario. By implementing these tests as part of routine 
maintenance, administrators can proactively address potential problems and 
validate that the cluster behaves as expected under various operational 
conditions.

### Verify Postgres

In the following example, commands verify Postgres installation and
connectivity:

```bash
# Check service status on RHEL
systemctl status postgresql-17

# Check service status on Debian
systemctl status postgresql@17-main

# Connect to database
psql -U admin -d myapp -c "SELECT version();"
```

### Verify Replication

In the following example, commands verify Spock replication status:

```bash
# Check Spock status
psql -x -U admin -d myapp -c "SELECT * FROM spock.node;"
psql -x -U admin -d myapp -c "SELECT * FROM spock.subscription;"

# Check replication lag
psql -x -U admin -d myapp -c "SELECT * FROM spock.lag_tracker;"
```

### Verify HA Cluster

In the following example, commands verify HA cluster health:

```bash
# Check etcd health
etcdctl endpoint health

# Check Patroni status
patronictl -c /etc/patroni/patroni.yaml list

# Check HAProxy status
systemctl status haproxy
```

### Verify Backups

In the following example, commands verify backup configuration:

```bash
# Check backup info
pgbackrest --stanza=pgedge-demo-1 info

# List backups
pgbackrest --stanza=pgedge-demo-1 info --output=json

# Verify latest backup
pgbackrest --stanza=pgedge-demo-1 check
```

## Common Workflows

Cluster management involves recurring operations that extend beyond initial 
deployment. This section covers essential procedures for modifying existing 
clusters, including adding new nodes, scaling HA zones, and handling 
configuration changes. Understanding these workflows helps administrators 
maintain clusters as requirements evolve.

The examples demonstrate best practices for each operation while highlighting 
potential limitations and recommended approaches to ensure cluster stability 
during modifications. Mastery of these workflows enables organizations to adapt 
their deployments seamlessly as workloads grow or architectural needs change.

### Adding a New Node to Simple Cluster

Adding a new node to a cluster should only be performed when database activity
is at a minimum or altogether absent. This Ansible collection does not yet 
leverage 
[Zero-Downtime Add Node](https://docs.pgedge.com/spock-v5/development/modify/zodan/zodan_readme/)
functionality.

1. Add the node to your inventory file:

    ```yaml
    pgedge:
      hosts:
        # existing nodes...
        node4.example.com:
          zone: 4
    ```

2. Run the playbook again to reconfigure the cluster:

    ```bash
    ansible-playbook playbook.yaml
    ```

3. Verify replication to the new node using the verification commands above.

### Expanding an HA Zone

!!! warning "Complex Operation"
    Adding nodes to an existing Patroni cluster requires careful coordination.
    Current roles do not fully support this operation.

The recommended approach includes the following steps:

- Plan for the final node count during initial deployment.
- Add all nodes to the inventory before the first run.
- Deploy the entire cluster together to ensure proper initialization.

### Changing Configuration

In most cases, modifying configuration parameters for the cluster simply 
consists of the following steps:

1. Update variables in the inventory file.
2. Re-run the playbook to apply changes.

Each role will make changes to managed configuration files and restart services 
where necessary.

!!! note "Limited Re-entrancy"
    The roles have limited re-entrancy; some configuration changes may require
    manual intervention or cluster rebuild.

### Disaster Recovery

When failures occur, having a well-defined recovery process minimizes downtime 
and data loss. This section outlines procedures for restoring Postgres 
instances from backups and handling zone failures in Ultra-HA configurations. 
The recovery strategies emphasize using dedicated recovery nodes to prevent 
cluster corruption and ensure clean rejoining of recovered nodes. Understanding 
these processes enables administrators to respond effectively to critical 
incidents, maintaining data integrity and service availability even in complex 
multi-zone environments where replication metadata must remain consistent 
across all nodes.

#### Restore from Backup

In the following example, commands restore a Postgres instance from backup:

```bash
# Stop Postgres
systemctl stop postgresql-17

# Remove data directory
rm -rf /var/lib/pgsql/17/data/*

# Restore from backup
pgbackrest --stanza=pgedge-1 --delta restore

# Start Postgres
systemctl start postgresql-17
```

!!! important "Separate Recovery Node"
    Perform recovery on an explicitly provisioned recovery node that remains
    separate from the existing cluster. External tools like pgEdge ACE can
    recover lost data into one of the remaining nodes. A recovered node cannot
    rejoin a multi-master Spock cluster due to mismatched node metadata;
    attempting to do so manually could corrupt the other cluster nodes.

#### Zone Failure in Ultra-HA

When an entire zone fails, the following sequence occurs:

1. The remaining zone continues operating without interruption.
2. Applications fail over to the surviving zone.
3. Once the failed zone recovers, Patroni restores local HA.
4. Spock re-synchronizes data automatically between zones.

## Best Practices

Follow these recommendations for successful deployments:

- Use Ansible Vault for all passwords and sensitive data.
- Test configurations in a staging environment before deploying to production.
- Document inventory files with clear comments explaining each setting.
- Store playbooks and inventory files in version control systems.
- Implement regular backups and test restore procedures periodically.
- Monitor replication lag between zones to ensure data synchronization.
- Plan capacity according to expected workload and growth.
- Use tags to enable partial playbook runs for specific components.
- Keep detailed notes documenting any manual changes to the cluster.
- Review deployment logs after each playbook run to catch issues.

## Next Steps

- Review [roles documentation](roles/index.md) for detailed role information.
- Understand [configuration options](configuration/index.md) for customization.
- Study [architecture patterns](architecture.md) for design considerations.
- Consult the [troubleshooting guide](troubleshooting/index.md) for common issues.

## Additional Resources

- [GitHub Repository](https://github.com/pgEdge/pgedge-ansible)
- [pgEdge Documentation](https://docs.pgedge.com/)
- [Spock Extension Guide](https://docs.pgedge.com/spock-v5/)
- [Patroni Documentation](https://patroni.readthedocs.io/en/latest/index.html)
- [pgBackRest Documentation](https://pgbackrest.org/)
