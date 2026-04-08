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
