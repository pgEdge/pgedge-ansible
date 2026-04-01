# Usage Examples

This page provides practical examples for deploying and verifying pgEdge
clusters, including customization patterns and common operational workflows.

## Before You Begin

Complete the following steps before running any playbook:

1. Install the collection as described in the
   [Installation](installation.md) guide.
2. Review the [Architecture](architecture.md) page to choose a topology.
3. Prepare target hosts with SSH access and `sudo` privileges.

## Multi-Stage Playbooks

Cluster designs that use multiple node groups require a play that targets
`all` hosts at the top of the playbook. This ensures Ansible populates
host variables for every server in the inventory before role-specific plays
begin. Some roles require variables for hosts outside their own group; for
example, a `pgedge` node needs zone information from nodes in the `backup`
group.

The following pattern satisfies this requirement without running `init_server`
twice:

```yaml
# Populate variables for all hosts first
- hosts: all
  roles: []

# Then run roles on specific groups
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - init_server
    - install_repos
    # ...
```

Alternatively, run `init_server` against `all` as the first play, as shown
in the Ultra-HA sample playbook.

## Single-Zone HA Cluster

A single-zone HA cluster provides automatic failover using Patroni and etcd,
with HAProxy routing connections to the current primary.

### Inventory File

The following example defines an HA cluster with all Postgres nodes in the
same zone:

```yaml
all:
  vars:
    ansible_user: pgedge

pgedge:
  vars:
    cluster_name: demo
    is_ha_cluster: true
    db_password: secure_password
    synchronous_mode: true
    zone: 1
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

The following example deploys a single-zone HA cluster with HAProxy:

```yaml
- hosts: all
  collections:
    - pgedge.platform
  roles:
    - init_server

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

- hosts: haproxy
  collections:
    - pgedge.platform
  roles:
    - setup_haproxy

- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - setup_pgedge
```

### What Gets Deployed

This configuration deploys the following components:

- Patroni manages the Postgres cluster in zone 1.
- An etcd cluster provides distributed consensus across the three nodes.
- HAProxy routes new connections to the current Patroni primary.
- Automatic failover activates when the primary becomes unavailable.

## Customization Examples

The following examples demonstrate common configuration overrides.

### Custom Database Configuration

The following inventory creates multiple databases with custom user accounts:

```yaml
pgedge:
  vars:
    db_names:
      - app_db
      - reporting_db
    db_user: appuser
    db_password: "{{ vault_db_password }}"
    pgedge_user: replication
    pgedge_password: "{{ vault_repl_password }}"
```

### Custom Port Configuration

The following inventory configures HAProxy to listen on port 5432 while
Postgres listens on port 5433, allowing HAProxy to run on the same node
as Postgres:

```yaml
pgedge:
  vars:
    pg_port: 5433
    proxy_port: 5432
```

### Strict Synchronous Replication

The following inventory enables strict synchronous replication, which
prevents writes when no synchronous replicas respond:

```yaml
pgedge:
  vars:
    is_ha_cluster: true
    synchronous_mode: true
    synchronous_mode_strict: true
```

### S3 Backup Configuration

The following inventory configures PgBackRest to use an AWS S3 bucket
instead of a dedicated SSH backup server:

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
    full_backup_schedule: "0 2 * * 0"
    diff_backup_schedule: "0 2 * * 1-6"
```

### Ansible Vault Integration

Use Ansible Vault to protect sensitive variables. The following command
creates an encrypted variable file:

```bash
ansible-vault create group_vars/pgedge/vault.yml
```

Place sensitive values in the vault file:

```yaml
vault_db_password: secure_password_123
vault_pgedge_password: replication_password_456
vault_backup_cipher: encryption_key_789
```

Reference vault variables in the inventory:

```yaml
pgedge:
  vars:
    db_password: "{{ vault_db_password }}"
    pgedge_password: "{{ vault_pgedge_password }}"
```

Run the playbook with the vault password:

```bash
ansible-playbook -i inventory.yaml playbook.yaml --ask-vault-pass
```

## Verifying a Deployment

After deployment, verify each component using the commands in this section.

### Verify Postgres

The following commands verify Postgres status and connectivity:

```bash
# Check service status on RHEL
systemctl status postgresql-17

# Check service status on Debian
systemctl status postgresql@17-main

# Connect to database
psql -U admin -d demo -c "SELECT version();"
```

### Verify Spock Replication

The following commands verify Spock node and subscription status:

```bash
# Check node registration
sudo -u postgres psql -x -U admin -d demo \
  -c "SELECT * FROM spock.node;"

# Check subscription status
sudo -u postgres psql -x -U admin -d demo \
  -c "SELECT * FROM spock.subscription;"
```

### Verify HA Cluster

The following commands verify the Patroni and etcd cluster state:

```bash
# Check Patroni cluster status
sudo -u postgres patronictl \
  -c /etc/patroni/patroni.yml list

# Check etcd endpoint health
sudo -u postgres /usr/local/etcd/etcdctl \
  --cacert=/etc/patroni/tls/ca.crt \
  --cert=/etc/patroni/tls/patroni.crt \
  --key=/etc/patroni/tls/patroni.key \
  endpoint health

# Check HAProxy status
systemctl status haproxy
```

### Verify Backups

The following commands verify the PgBackRest backup repository:

```bash
# Display backup repository info
pgbackrest --stanza=pgedge-demo-1 info

# Verify the latest backup
pgbackrest --stanza=pgedge-demo-1 check
```

## Common Workflows

This section covers recurring operational tasks.

### Test HA Failover

The following command triggers a manual Patroni failover to verify that
HAProxy redirects connections to the new primary:

```bash
sudo -u postgres patronictl \
  -c /etc/patroni/patroni.yml failover demo
```

After the failover, connections through HAProxy continue automatically
without application changes.

### Adding a Node to a Simple Cluster

Add new nodes to a cluster only when database activity is at a minimum.
The collection does not currently use
[Zero-Downtime Add Node](https://docs.pgedge.com/spock-v5/development/modify/zodan/zodan_readme/)
functionality.

1. Add the new node to the inventory with a new zone number.
2. Run the playbook again to reconfigure the full cluster.
3. Verify Spock replication to the new node using the commands above.

### Disaster Recovery

When a node fails in a Spock cluster, restore it on a provisioned recovery
node that is separate from the existing cluster. The following commands
restore a Postgres instance from a PgBackRest backup:

```bash
# Stop Postgres
systemctl stop postgresql-17

# Clear the data directory
rm -rf /var/lib/pgsql/17/data/*

# Restore from backup
pgbackrest --stanza=pgedge-1 --delta restore

# Start Postgres
systemctl start postgresql-17
```

A recovered node cannot rejoin a Spock cluster by simple reconnection
because the cluster metadata will have diverged. Use
[pgEdge ACE](https://docs.pgedge.com/ace/) to reconcile data differences
and reintegrate the node safely.

## Next Steps

- The [Configuration Reference](configuration.md) lists all available
  parameters and their defaults.
- The [Troubleshooting](troubleshooting.md) guide covers common deployment
  issues.
- The [Role Reference](roles.md) describes what each role does in detail.
