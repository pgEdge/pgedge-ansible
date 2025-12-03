# etcd Configuration

Settings here are generally only used by the `install_etcd` and `setup_etcd` roles. In most cases, the default are sufficient to built a fully operational DCS layer for Patroni.

## etcd_version

- **Type:** String
- **Default:** `3.6.5`
- **Description:** etcd version to download and install

```yaml
etcd_version: "3.6.7"
```

## etcd_base_url

- **Type:** String
- **Default:** `https://github.com/etcd-io/etcd/releases/download/v{{ etcd_version }}`
- **Description:** Base URL for etcd downloads. Can be customized for air-gapped environments or local mirrors.

```yaml
etcd_base_url: "https://my-mirror.local/etcd/v{{ etcd_version }}"
```

## etcd_checksum

- **Type:** String
- **Default:** `sha256:{{ etcd_base_url }}/SHA256SUMS`
- **Description:** URL to SHA256 checksum file for download verification

## etcd_package

- **Type:** String
- **Default:** `etcd-v{{ etcd_version }}-linux-amd64`
- **Description:** etcd package filename (architecture-specific)

```yaml
etcd_package: etcd-v{{ etcd_version }}-linux-arm64`
```

## etcd_user

- **Type:** String
- **Default:** `etcd`
- **Description:** System user for running etcd service

```yaml
etcd_user: etcd-sys
```

## etcd_group

- **Type:** String
- **Default:** `etcd`
- **Description:** System group for etcd service

```yaml
etcd_group: etcd-sys
```

## etcd_install_dir

- **Type:** String
- **Default:** `/usr/local/etcd`
- **Description:** Directory where etcd binaries are installed

```yaml
etcd_install_dir: /opt/etcd
```

## etcd_config_dir

- **Type:** String
- **Default:** `/etc/etcd`
- **Description:** Directory for etcd configuration files

```yaml
etcd_install_dir: /usr/local/etc/etcd
```

## etcd_data_dir

- **Type:** String
- **Default:** `/var/lib/etcd`
- **Description:** Directory for etcd data storage and cluster state

```yaml
etcd_data_dir: /data/etcd
```
