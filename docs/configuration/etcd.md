# etcd Configuration

The `install_etcd` and `setup_etcd` roles manage the parameters described on
this page. In most cases, the defaults are sufficient to build a fully
operational distributed coordination layer for Patroni.

## etcd_version

- Type: String
- Default: `3.6.5`
- Description: This parameter specifies the etcd version to install from the
  pgEdge package repository.

In the following example, the inventory specifies a custom etcd version:

```yaml
etcd_version: "3.6.7"
```

## etcd_user

- Type: String
- Default: `etcd`
- Description: This parameter specifies the system user for running the etcd
  service.

In the following example, the inventory specifies a custom etcd user:

```yaml
etcd_user: etcd-sys
```

## etcd_group

- Type: String
- Default: `etcd`
- Description: This parameter specifies the system group for the etcd service.

## etcd_install_dir

- Type: String
- Default: `/usr/local/etcd`
- Description: This parameter specifies the directory where etcd binaries are
  installed.

In the following example, the inventory specifies a custom installation
directory:

```yaml
etcd_install_dir: /opt/etcd
```

## etcd_config_dir

- Type: String
- Default: `/etc/etcd`
- Description: This parameter specifies the directory for etcd configuration
  files.

In the following example, the inventory specifies a custom configuration
directory:

```yaml
etcd_config_dir: /usr/local/etc/etcd
```

## etcd_data_dir

- Type: String
- Default: `/var/lib/etcd`
- Description: This parameter specifies the directory for etcd data storage
  and cluster state.

In the following example, the inventory specifies a custom data directory:

```yaml
etcd_data_dir: /data/etcd
```

## etcd_tls_dir

- Type: String
- Default: `/etc/etcd/tls`
- Description: This parameter specifies the full path where etcd stores TLS
  certificates and keys.

In the following example, the inventory specifies a custom TLS directory:

```yaml
etcd_tls_dir: /etc/ssl/etcd
```

## patroni_tls_dir

- Type: String
- Default: `/etc/patroni/tls`
- Description: This parameter specifies the directory where the `install_patroni`
  and `setup_patroni` roles install Patroni TLS certificates necessary for
  communicating with etcd.

In the following example, the inventory specifies a custom Patroni TLS
directory:

```yaml
patroni_tls_dir: "/etc/ssl/certs/patroni"
```

## etcd_ca_cert and etcd_ca_key

- Type: String (PEM)
- Default: (none - an authority is generated on the Ansible controller)
- Description: These parameters supply the certificate authority that signs
  etcd's server and peer certificates and every node's Patroni client
  certificate. Set them together or not at all. When unset, the collection
  generates an authority on the controller under `tls/etcd/` beside the
  playbook, exactly as it always has.

### Why you may want to set them

The generated authority is the one artifact in `tls/` that nothing can
recreate. `setup_etcd` creates it, and `setup_etcd` skips itself entirely once
the etcd data directory exists — so on a running cluster there is no code path
that will generate it again. `setup_patroni` only ever *signs* against it.

A controller that loses that directory therefore cannot add a replica, rebuild
a node, recover the cluster, or even re-run the deployment playbook. It fails
with:

```
The CA certificate file tls/etcd/ca.crt does not exist
```

`tls/` is in `.gitignore`, correctly — it holds a private key. Supplying the
authority from the inventory instead puts it where every other secret this
collection needs already lives, under Ansible Vault beside `db_password`, and
leaves the staging directory as a cache rather than the only copy.

### Supplying them

Use a block scalar, in a vault-encrypted variable file:

```yaml
etcd_ca_cert: |
  -----BEGIN CERTIFICATE-----
  MIIF...
  -----END CERTIFICATE-----
etcd_ca_key: |
  -----BEGIN PRIVATE KEY-----
  MIIJ...
  -----END PRIVATE KEY-----
```

!!! warning "Not on the command line"
    `-e etcd_ca_cert="$(cat ca.crt)"` does not work. Ansible's `-e key=value`
    form does not carry newlines, so the PEM arrives truncated and the
    certificate is unusable. Pass a file instead — `-e @ca-vars.yml` — or put
    the values in the inventory.

To capture the authority an existing cluster already uses, read it from the
controller that deployed it:

```bash
cd sample-playbooks/ultra-ha
ansible-vault encrypt_string --name etcd_ca_key "$(cat tls/etcd/ca.key)"
ansible-vault encrypt_string --name etcd_ca_cert "$(cat tls/etcd/ca.crt)"
```

### Changing them

Don't, on a live cluster. The nodes trust the authority their etcd was built
with, and signing new certificates against a different one leaves no node able
to reach the configuration store. The collection refuses a supplied authority
that differs from the one already staged, rather than breaking the cluster
quietly:

```
etcd_ca_cert does not match the certificate authority already staged in
tls/etcd/ca.crt.
```

Replacing the authority of a running cluster means rebuilding its configuration
store. See `recovery_reset_dcs` in
[Recovering a Cluster from Backup](../recovery.md).
