# Usage Examples

This page provides practical examples for deploying pgEdge clusters using the Ansible collection, from simple configurations to complex high-availability setups.

## Before You Begin

Ensure you have:

1. [Installed the collection](installation.md)
2. Reviewed the [architecture patterns](architecture.md)
3. Understood the [configuration variables](configuration.md)
4. Prepared your target hosts

!!! important "Multi-Stage Playbooks"
    Any cluster design which requires multiple node types will likely restrict certain roles to specific node groups. Our sample playbooks always include the following play at the very top in this case:

    ```yaml
    - hosts: all
      collections:
      - pgedge.platform
      roles:
      - init_server
    ```

    This ensures Ansible host variables are populated for every server in the inventory. Some roles may require variables for hosts that are not part of the intended role group. For example, a `pgedge` node may need to know information about nodes in the `backup` group. If you'd rather not repeatedly invoke `init_server` at the top of every playbook, ensure hostvar population using a dummy play like this at the top of the playbook:

    ```yaml
    - hosts: all
      roles: []
    ```

## Sample Playbooks

The repository includes sample playbooks in the `sample-playbooks/` directory:

- **simple-cluster** - Standard three-node cluster
- **ultra-ha** - Ultra-HA cluster with multiple zones

These serve as templates for your own deployments.

## Simple Three-Node Cluster

The simplest deployment consists of three pgEdge nodes with direct replication between them.

### Inventory File

Create `inventory.yaml`:

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

Create `playbook.yaml`:

```yaml
---
- hosts: pgedge
  collections:
    - pgedge.platform

  roles:
    - init_server         # Prepare servers
    - install_repos       # Configure repositories
    - install_pgedge      # Install PostgreSQL
    - setup_postgres      # Initialize database
    - setup_pgedge        # Configure multi-master replication
```

### Running the Playbook

```bash
ansible-playbook -i inventory.yaml playbook.yaml
```

### What Gets Deployed

This creates:

- PostgreSQL 17 on each node
- Spock extension for multi-master replication
- Full-mesh replication between all three nodes
- Database named `myapp` on all nodes

### Connecting to the Cluster

Connect to any node:

```bash
psql -h node1.example.com -U admin myapp
```

Data written to any node replicates to all others.

## High-Availability Single-Zone Cluster

Deploy a single-zone HA cluster with automatic failover.

### Inventory File

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

- Patroni-managed PostgreSQL cluster in zone 1
- etcd for distributed consensus
- HAProxy for connection routing to the current primary node
- Automatic failover within the zone

### Testing Failover

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

The most robust configuration with HA within zones and replication between zones.

### Inventory File

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

- Two Patroni clusters (one per zone)
- etcd cluster in each zone
- HAProxy in each zone
- Spock replication between zones through HAProxy
- Automated backups to dedicated backup servers
- Full redundancy at all levels

### Connection Architecture

```
Application (Zone 1) -> proxy-z1 -> Patroni Cluster Zone 1 -> Spock -> Patroni Cluster Zone 2
Application (Zone 2) -> proxy-z2 -> Patroni Cluster Zone 2 -> Spock -> Patroni Cluster Zone 1
```

## Adding Backups to Existing Cluster

Add backup capability to an already-deployed cluster.

### S3 Backups

Update your inventory:

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

Run backup setup:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_backrest
    - setup_backrest
```

### SSH Backups with Dedicated Server

Add backup hosts to inventory:

```yaml
backup:
  hosts:
    backup-server.example.com:
      zone: 1
```

Update pgedge group in inventory:

```yaml
pgedge:
  vars:
    backup_repo_type: ssh
```

Run backup setup on all relevant hosts:

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

### Custom PostgreSQL Version

Use the latest and greatest Postgres version.

```yaml
pgedge:
  vars:
    pg_version: 18
```

### Custom Database Configuration

Install and set up Spock clusters in three different databases.

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

Set up HAProxy on the same node as Postgres by assigning the standard Postgres port (5432) to HAProxy, and moving Postgres to another port.

```yaml
pgedge:
  vars:
    pg_port: 5433
    proxy_port: 5432  # HAProxy listens on standard port
```

### Strict Synchronous Replication

Enable synchronous replication, and enforce it by preventing writes on the Primary if there are no online synchronous replicas.

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    synchronous_mode_strict: true  # Prevents writes if replicas unavailable
```

## Testing Your Deployment

### Verify PostgreSQL

```bash
# Check service status on RHEL
systemctl status postgresql-17

# Check service status on Debian
systemctl status postgresql@17-main

# Connect to database
psql -U admin -d myapp -c "SELECT version();"
```

### Verify Replication

```bash
# Check Spock status
psql -x -U admin -d myapp -c "SELECT * FROM spock.node;"
psql -x -U admin -d myapp -c "SELECT * FROM spock.subscription;"

# Check replication lag
psql -x -U admin -d myapp -c "SELECT * FROM spock.lag_tracker;"
```

### Verify HA Cluster

```bash
# Check etcd health
etcdctl endpoint health

# Check Patroni status
patronictl -c /etc/patroni/patroni.yaml list

# Check HAProxy status
systemctl status haproxy
```

### Verify Backups

```bash
# Check backup info
pgbackrest --stanza=pgedge-demo-1 info

# List backups
pgbackrest --stanza=pgedge-demo-1 info --output=json 

# Verify latest backup
pgbackrest --stanza=pgedge-demo-1 check
```

## Common Workflows

### Adding a New Node to Simple Cluster

1. Add node to inventory:

```yaml
pgedge:
  hosts:
    # existing nodes...
    node4.example.com:
      zone: 4
```

2. Run playbook again to reconfigure cluster:

```bash
ansible-playbook playbook.yaml
```

3. Verify replication to new node

### Expanding an HA Zone

!!! warning "Complex Operation"
    Adding nodes to an existing Patroni cluster requires careful coordination. This is not fully supported by the current roles.

Currently, the best approach is:

1. Plan for final node count during initial deployment
2. Add nodes to inventory before first run
3. Deploy entire cluster together

### Changing Configuration

1. Update variables in inventory
2. Re-run playbook

!!! note "Limited Re-entrancy"
    The roles have limited re-entrancy. Some configuration changes may require manual intervention or cluster rebuild.

### Disaster Recovery

#### Restore from Backup

```bash
# Stop PostgreSQL
systemctl stop postgresql-17

# Remove data directory
rm -rf /var/lib/pgsql/17/data/*

# Restore from backup
pgbackrest --stanza=pgedge-1 --delta restore

# Start PostgreSQL
systemctl start postgresql-17
```

!!! important "Separate Recovery Node"
    Recovery should be done in an explicitly provisioned "recovery node" separate from the existing cluster. Then an external tool like pgEdge ACE can recover lost data into one of the remaining nodes. It is not currently possible for a recovered node to re-join a multi-master Spock cluster due to mismatched node metadata. Doing so manually could result in corruption of the other remaining cluster nodes.

#### Zone Failure in Ultra-HA

If an entire zone fails:

1. Remaining zone continues operating
2. Applications fail over to surviving zone
3. Once failed zone recovers, Patroni restores local HA
4. Spock re-synchronizes data automatically

## Best Practices

1. **Use Ansible Vault** for all passwords
2. **Test in staging** before production
3. **Document your inventory** with comments
4. **Version control** your playbooks and inventory
5. **Regular backups** - test restore procedures
6. **Monitor replication lag** between zones
7. **Plan capacity** for expected workload
8. **Use tags** for partial playbook runs
9. **Keep detailed notes** of any manual changes
10. **Review logs** after deployment

## Troubleshooting Tips

### Playbook Failures

```bash
# Run with increased verbosity
ansible-playbook playbook.yaml -vvv

# Check mode (dry run)
ansible-playbook playbook.yaml --check
```

### Connection Issues

```bash
# Test connectivity
ansible all -i inventory.yaml -m ping

# Check SSH access
ansible all -i inventory.yaml -m shell -a "hostname"
```

### Role-Specific Issues

See the troubleshooting sections in individual [role documentation](roles/index.md).

## Next Steps

- Review [roles documentation](roles/index.md) for detailed information on each component
- Understand [configuration options](configuration.md) for customization
- Study [architecture patterns](architecture.md) for design considerations
- Join the pgEdge community for support and discussion

## Additional Resources

- [GitHub Repository](https://github.com/pgEdge/pgedge-ansible)
- [pgEdge Documentation](https://docs.pgedge.com/)
- [Spock Extension Guide](https://docs.pgedge.com/spock-v5/)
- [Patroni Documentation](https://patroni.readthedocs.io/en/latest/index.html)
- [pgBackRest Documentation](https://pgbackrest.org/)
