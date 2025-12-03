# System Configuration

Settings here will affect the base operating-system. These settings have been tested on Debian and RedHat variant Linux systems, so should work on Ubuntu, Fedora, Rocky, and similar systems.

## debug_pgedge

- **Type:** Boolean
- **Default:** `true`
- **Description:** Configure kernel settings to retain core files from process crashes for debugging.

```yaml
debug_pgedge: false
```

## disable_selinux

- **Type:** Boolean
- **Default:** `true`
- **Description:** Disables SELinux when specified. May require a reboot.

```yaml
disable_selinux: false
```

## manage_host_file

- **Type:** Boolean
- **Default:** `true`
- **Description:** Automatically add all cluster hosts to `/etc/hosts` on every node. Disable if using external DNS or IP addresses in inventory.

```yaml
manage_host_file: false
```
