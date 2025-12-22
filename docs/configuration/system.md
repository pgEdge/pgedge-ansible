# System Configuration

The following settings affect the base operating system. We have tested these settings on Debian and RedHat variant Linux systems, so they should work on Ubuntu, Fedora, Rocky, and similar systems.

## debug_pgedge

- Type: Boolean
- Default: `true`
- Description: This parameter configures kernel settings to retain core files from process crashes for debugging.

```yaml
debug_pgedge: false
```

## disable_selinux

- Type: Boolean
- Default: `true`
- Description: This parameter disables SELinux when you enable the parameter. A reboot may be required.

```yaml
disable_selinux: false
```

## manage_host_file

- Type: Boolean
- Default: `true`
- Description: This parameter automatically adds all cluster hosts to `/etc/hosts` on every node. You can disable this parameter if you use external DNS or IP addresses in your inventory.

```yaml
manage_host_file: false
```
