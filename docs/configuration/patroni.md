# Patroni Configuration

Settings here define how Patroni operates, and are mainly used by the `install_patroni` and `setup_patroni` roles.

## patroni_bin_dir

- **Type:** String
- **Default:** `{{ pg_home }}/.local/bin`
    - For RHEL-family systems: `/var/lib/pgsql/.local/bin`
    - For Debian-family systems: `/var/lib/postgresql/.local/bin`
- **Description:** Directory where Patroni binaries are installed (pipx install location)

```yaml
patroni_bin_dir: "/var/lib/pgsql/.local/bin"
```

## patroni_config_dir

- **Type:** String
- **Default:** `/etc/patroni`
- **Description:** Directory for Patroni configuration files

```yaml
patroni_config_dir: "/etc/patroni"
```
