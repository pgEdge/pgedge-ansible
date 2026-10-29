# Cluster Configuration

The collection uses cluster-wide configuration variables across multiple roles.
These settings define the basic operation, identity, and user accounts for the
cluster.

## cluster_name

- Type: String
- Default: `demo`
- Description: This parameter specifies the canonical name for the cluster.
  The collection uses this name for descriptive items and generated values
  such as stanza names and etcd key prefixes.

In the following example, the inventory specifies a production cluster name:

```yaml
cluster_name: production-cluster
```

## zone

- Type: Integer
- Default: `1`
- Description: This parameter specifies the zone or region identifier for a
  node. The zone serves two purposes: organizing nodes into logical groups and
  providing the Snowflake sequence ID. In simple clusters, use one node per
  zone. In HA clusters, assign multiple nodes to the same zone to form a
  Patroni cluster.

In the following example, the inventory assigns each node to a separate zone:

```yaml
hosts:
  node1.example.com:
    zone: 1
  node2.example.com:
    zone: 2
```

## repo_name

- Type: String
- Default: `release`
- Options: `release`, `staging`, `daily`
- Description: This parameter controls which pgEdge repository tier to use
  for software installation. Contact the pgEdge team before using `staging`
  or `daily` in production environments.

In the following example, the inventory uses the release repository:

```yaml
repo_name: release
```

## repo_prefix

- Type: String
- Default: (none)
- Description: This parameter enables installation of specific custom or
  automated builds. Contact pgEdge staff for valid values.

## repo_url

- Type: String
- Default: (none)
- Description: This parameter names a package repository of your own, such
  as a mirror or a caching proxy, for the `install_repos` role to use in place
  of the pgEdge repository servers. When this parameter is empty, the role
  installs the `pgedge-release` package, which points the host at the pgEdge
  servers. When the parameter is set, the role removes that package and writes
  the equivalent repository definition, pointing at this URL instead. The URL
  must begin with `http://`, `https://`, or `file:///`.

In the following example, the inventory points RHEL hosts at a caching proxy
of `dnf.pgedge.com` and Debian hosts at a proxy of `apt.pgedge.com`:

```yaml
rhel_hosts:
  vars:
    repo_url: https://artifacts.example.com/pgedge-dnf
debian_hosts:
  vars:
    repo_url: https://artifacts.example.com/pgedge-apt
```

## repo_layout

- Type: String
- Default: `upstream`
- Options: `upstream`, `mirror`
- Description: This parameter describes how the repository at `repo_url`
  arranges its contents. The `upstream` layout matches the pgEdge servers
  themselves, which is the arrangement a caching proxy or a copy of a
  repository server keeps. In this layout, `repo_url` replaces
  `https://dnf.pgedge.com` on RHEL hosts or `https://apt.pgedge.com` on Debian
  hosts, and `repo_name` selects the tier as usual. The `mirror` layout matches
  a mirror built by a proposed pgEdge mirror procedure, which keeps every
  platform under one URL and mirrors only the `release` tier.

In the following example, the inventory points every host at a pgEdge mirror,
whatever the operating system:

```yaml
repo_url: http://mirror.example.com/pgedge
repo_layout: mirror
```

## repo_gpg_key

- Type: String
- Default: (none)
- Description: This parameter specifies the URL of the key that signs pgEdge
  packages. When this parameter is empty, the `install_repos` role fetches the
  key from where the layout keeps the key under `repo_url`, so a host on an
  isolated network needs no access to the pgEdge servers. The role always
  checks package signatures. Use this parameter only together with `repo_url`.

In the following example, the inventory fetches the key from an internal
server:

```yaml
repo_url: https://artifacts.example.com/pgedge-dnf
repo_gpg_key: https://keys.example.com/pgedge-rsa.pub
```

## db_names

- Type: List
- Default: `[demo]`
- Description: This parameter specifies the database names for the Spock
  cluster. At least one name is required. The roles create any missing
  databases automatically and install the Spock and Snowflake extensions in
  each.

In the following example, the inventory specifies multiple database names:

```yaml
db_names:
  - app_db
  - reporting_db
```

## db_user

- Type: String
- Default: `admin`
- Description: This parameter specifies the primary database username. This
  username must differ from the OS user running Ansible.

In the following example, the inventory specifies a custom database user:

```yaml
db_user: appuser
```

## db_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the database user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
db_password: "{{ vault_db_password }}"
```

## pgedge_user

- Type: String
- Default: `pgedge`
- Description: This parameter specifies the database username for pgEdge
  inter-node logical replication. The cluster uses this account for Spock
  operations between nodes.

## pgedge_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the pgEdge
  replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
pgedge_password: "{{ vault_pgedge_password }}"
```

## is_ha_cluster

- Type: Boolean
- Default: `false`
- Description: This parameter enables high availability features. When `true`,
  the collection installs and configures etcd, Patroni, and HAProxy on the
  appropriate nodes.

In the following example, the inventory enables high availability mode:

```yaml
is_ha_cluster: true
```

## replication_user

- Type: String
- Default: `replicator`
- Description: This parameter specifies the username for Patroni streaming
  replication. This setting only applies to HA clusters.

## replication_password

- Type: String
- Default: `secret`
- Description: This parameter specifies the password for the Patroni
  replication user.

In the following example, the inventory retrieves the password from Ansible
Vault:

```yaml
replication_password: "{{ vault_replication_password }}"
```

## synchronous_mode

- Type: Boolean
- Default: `false`
- Description: This parameter enables Patroni management of `synchronous_commit`
  and `synchronous_standby_names` based on cluster state.

## synchronous_mode_strict

- Type: Boolean
- Default: `false`
- Description: This parameter enforces synchronous commit when `synchronous_mode`
  is enabled, even if no synchronous replicas are available. Enabling this
  setting can prevent writes during replica failures.

!!! warning "Data Availability Trade-off"
    Strict synchronous mode prioritizes data durability over availability.
    The cluster blocks writes if synchronous replicas become unavailable.

## tls_validity_days

- Type: Integer
- Default: `3560`
- Description: This parameter controls the validity period in days for TLS
  certificates generated by the collection. The default of approximately ten
  years avoids cluster disruptions due to certificate expiration.

In the following example, the inventory sets a one-year certificate validity:

```yaml
tls_validity_days: 365
```

## spock_version

- Type: String
- Default: `5.0.4`
- Description: This parameter specifies the minimum version of the Spock
  extension to install. The latest available version is always installed.

!!! warning "Security"
    Never commit passwords to version control. Use Ansible Vault or environment
    variables for any `_password` parameters.
