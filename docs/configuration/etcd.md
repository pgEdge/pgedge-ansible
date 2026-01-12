# etcd Configuration

The `install_etcd` and `setup_etcd` are the principal owners for the parameters described in this page. In most cases, the defaults are sufficient to build a fully operational DCS layer for Patroni.

## etcd_version

- Type: String
- Default: `3.6.5`
- Description: This parameter specifies the etcd version to download and install.

```yaml
etcd_version: "3.6.7"
```

## etcd_base_url

- Type: String
- Default: `https://github.com/etcd-io/etcd/releases/download/v{{ etcd_version }}`
- Description: This parameter specifies the base URL for etcd downloads. You can customize this parameter for air-gapped environments or local mirrors.

```yaml
etcd_base_url: "https://my-mirror.local/etcd/v{{ etcd_version }}"
```

## etcd_checksum

- Type: String
- Default: `sha256:{{ etcd_base_url }}/SHA256SUMS`
- Description: This parameter specifies the URL to the SHA256 checksum file for download verification.

## etcd_package

- Type: String
- Default: `etcd-v{{ etcd_version }}-linux-amd64`
- Description: This parameter specifies the etcd package filename (architecture-specific).

```yaml
etcd_package: etcd-v{{ etcd_version }}-linux-arm64
```

## etcd_user

- Type: String
- Default: `etcd`
- Description: This parameter specifies the system user for running the etcd service.

```yaml
etcd_user: etcd-sys
```

## etcd_group

- Type: String
- Default: `etcd`
- Description: This parameter specifies the system group for the etcd service.

```yaml
etcd_group: etcd-sys
```

## etcd_install_dir

- Type: String
- Default: `/usr/local/etcd`
- Description: This parameter specifies the directory where etcd binaries are installed.

```yaml
etcd_install_dir: /opt/etcd
```

## etcd_config_dir

- Type: String
- Default: `/etc/etcd`
- Description: This parameter specifies the directory for etcd configuration files.

```yaml
etcd_config_dir: /usr/local/etc/etcd
```

## etcd_data_dir

- Type: String
- Default: `/var/lib/etcd`
- Description: This parameter specifies the directory for etcd data storage and cluster state.

```yaml
etcd_data_dir: /data/etcd
```
