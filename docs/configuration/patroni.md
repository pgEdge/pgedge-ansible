# Patroni Configuration

The following settings define how Patroni operates. The `install_patroni` and `setup_patroni` roles mainly use these settings.

## patroni_bin_dir

- Type: String
- Default: `{{ pg_home }}/.local/bin`

    - For RHEL-family systems: `/var/lib/pgsql/.local/bin`
    - For Debian-family systems: `/var/lib/postgresql/.local/bin`

- Description: This parameter specifies the directory where the roles install Patroni binaries (pipx install location).

```yaml
patroni_bin_dir: "/var/lib/pgsql/.local/bin"
```

## patroni_config_dir

- Type: String
- Default: `/etc/patroni`
- Description: This parameter specifies the directory for Patroni configuration files.

```yaml
patroni_config_dir: "/etc/patroni"
```
