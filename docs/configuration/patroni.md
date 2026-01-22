# Patroni Configuration

The following settings define how Patroni operates. The `install_patroni` and
`setup_patroni` roles use these settings to configure the HA management layer.

## patroni_bin_dir

- Type: String
- Default: `{{ pg_home }}/.local/bin`

    - For RHEL-family systems, the default is 
      `/var/lib/pgsql/.local/bin`.
    - For Debian-family systems, the default is 
      `/var/lib/postgresql/.local/bin`.

- Description: This parameter specifies the directory where the roles install
  Patroni binaries via the pipx install location.

```yaml
patroni_bin_dir: "/var/lib/pgsql/.local/bin"
```

## patroni_config_dir

- Type: String
- Default: `/etc/patroni`
- Description: This parameter specifies the directory for Patroni configuration
  files.

```yaml
patroni_config_dir: "/etc/patroni"
```
