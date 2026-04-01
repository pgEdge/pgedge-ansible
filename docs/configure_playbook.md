# Configuring a Playbook

The cluster deployed by a playbook may host high-availability nodes that
reside in a single zone or in multiple zones; you can also customize a
playbook with other [configuration options](#customizing-the-configuration).

## Configuring a Single-Zone HA Playbook File

The playbook in the following example deploys a single-zone HA cluster using
HAProxy; you can customize this deployment with the code samples that follow
this section:

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

This configuration deploys the following components:

- Patroni manages the Postgres cluster in zone 1.
- An etcd cluster provides distributed consensus across the three nodes.
- HAProxy routes new connections to the current Patroni primary.
- Automatic failover activates when the primary becomes unavailable.


## Configuring Multi-Zone Playbooks

Cluster designs that use multiple node groups require a playbook that targets
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


## Customizing the Configuration

The following examples demonstrate some common configuration overrides you may want to incorporate into 
[this playbook](usage.md#single-zone-ha-playbook-file).

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

### Strict Synchronous Replication Configuration

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

### Ansible Vault Integration Configuration

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

