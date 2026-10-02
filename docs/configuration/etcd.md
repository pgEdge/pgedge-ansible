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
  generates an authority under `tls/etcd/` beside the playbook on the first
  deployment.

A generated authority exists only on the controller that ran that first
deployment. Any other controller — a colleague's workstation, a fresh CI
runner, a new checkout — cannot sign certificates for the cluster, so it
cannot add a replica, rebuild a node, recover the cluster, or re-run the
deployment.

Before signing anything, the collection reads the authority every running etcd
member trusts and compares it with the one on the controller. When the
controller has none, it stops rather than generating a new one:

```
This cluster's etcd already trusts a certificate authority, and this
controller does not hold it: etcd_ca_cert is unset and there is no
tls/etcd/ca.crt beside the playbook.
```

It also stops when the controller's authority, supplied or staged, differs
from the one the members trust. Without that check, adding a node from such a
controller would generate a new authority and reissue every node's Patroni
certificate against it, and no node could reach etcd afterwards. A new
cluster, with no etcd members yet, is the only case where an authority is
generated.

The controller also stops when `tls/etcd/` holds `ca.crt` without `ca.key`, or
a `ca.key` that is not the key of `ca.crt`. Copy both files together. A
supplied `etcd_ca_key` that is not the key of `etcd_ca_cert` is refused the
same way.

Every one of these checks runs before a supplied authority is written to
`tls/etcd/`, so one that is refused is not left staged for the next run to
find. And because an unanswered member is not an agreeing one, the collection
also stops when any pgEdge host cannot be reached to ask, naming the host.

Supplying the authority from an Ansible Vault file lets any controller with
the vault password manage the cluster. Automated or disposable environments
should always set these parameters.

### Step 1: Obtain the authority

You need two files: `ca.crt`, the certificate, and `ca.key`, its private key.
Where they come from depends on whether the cluster exists yet.

**For a new cluster**, generate them before the first deployment:

```bash
openssl req -x509 -newkey rsa:4096 -noenc \
  -keyout ca.key -out ca.crt -days 7300 -subj "/CN=etcd-ca" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"
```

This requires OpenSSL 3.0 or later; with OpenSSL 1.1.1, replace `-noenc` with
`-nodes`. The `-days` value is how long the cluster can run on this authority.
It should comfortably exceed
[`tls_validity_days`](cluster.md#tls_validity_days), because every certificate
it signs is valid for that long from the day it is signed; 7300 days is 20
years.

**For an existing cluster**, you must use the authority it was deployed with.
Copy the files from the `tls/etcd/` directory beside the playbook on the
controller that ran the first deployment:

```bash
cp /path/to/playbook/tls/etcd/ca.crt /path/to/playbook/tls/etcd/ca.key .
```

If that controller is gone, the authority cannot be recovered, and the
cluster's configuration store must be rebuilt under a new one. See
`recovery_reset_dcs` in [Recovering a Cluster from Backup](../recovery.md).

### Step 2: Store it in the vault

Run the following from the directory holding `ca.crt` and `ca.key`, replacing
`/path/to/inventory` with the directory that holds your inventory file. It
writes both files into a variable file readable only by you, encrypts it into
the inventory, and removes the unencrypted copies:

```bash
(
  set -e
  umask 077
  inv=/path/to/inventory/group_vars/pgedge
  tmp=$(mktemp ./etcd_ca.XXXXXX)
  trap 'rm -f "$tmp"' EXIT
  {
    echo "vault_etcd_ca_cert: |"; sed 's/^/  /' ca.crt
    echo "vault_etcd_ca_key: |";  sed 's/^/  /' ca.key
  } > "$tmp"
  mkdir -p "$inv"
  ansible-vault encrypt --output "$inv/etcd_ca.yml" "$tmp"
  rm ca.crt ca.key
)
```

The unencrypted variable file never reaches the inventory: it is built beside
`ca.key`, and only the encrypted result is written there. If any step fails —
most often a mistyped vault password confirmation — the temporary file is
removed, nothing is written to the inventory, and `ca.crt` and `ca.key` are
left where they are, so you can run it again.

`ansible-vault encrypt` prompts for a vault password. If you already keep
other secrets in a vault, use the same password so a single
`--ask-vault-pass` unlocks both.

Then reference the vaulted values in the inventory:

```yaml
pgedge:
  vars:
    etcd_ca_cert: "{{ vault_etcd_ca_cert }}"
    etcd_ca_key: "{{ vault_etcd_ca_key }}"
```

Run playbooks with the vault password as usual:

```bash
ansible-playbook -i inventory.yaml playbook.yaml --ask-vault-pass
```

For unattended runs, pass `--vault-password-file` instead, with the password
supplied by your automation's secret store.

!!! warning "Not on the command line"
    `-e etcd_ca_cert="$(cat ca.crt)"` does not work. Ansible's `-e key=value`
    form does not carry newlines, so the certificate arrives truncated and
    unusable. Pass a file instead — `-e @etcd_ca.yml` — or use the inventory
    as shown above.

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
