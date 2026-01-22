# System Configuration

These parameters affect the base operating system configuration on inventory
hosts. The current testing environment includes Debian and RedHat variant Linux
systems; these options work on Ubuntu, Fedora, Rocky, and similar distributions.

## debug_pgedge

This parameter configures kernel settings to retain core files from process
crashes for debugging purposes.

| Attribute | Value |
|-----------|-------|
| Type | Boolean |
| Default | `true` |

In the following example, the inventory disables core file retention:

```yaml
pgedge:
  vars:
    debug_pgedge: false
```

## disable_selinux

This parameter controls whether SELinux remains enabled on inventory hosts.
Setting this parameter to `true` disables SELinux; the system may require a
reboot for the change to take effect.

| Attribute | Value |
|-----------|-------|
| Type | Boolean |
| Default | `true` |

In the following example, the inventory keeps SELinux enabled:

```yaml
pgedge:
  vars:
    disable_selinux: false
```

## manage_host_file

This parameter controls automatic management of the `/etc/hosts` file on all
cluster nodes. When enabled, the collection adds all cluster hosts to the hosts
file on every node. Disable this parameter if you use external DNS or IP
addresses in your inventory.

| Attribute | Value |
|-----------|-------|
| Type | Boolean |
| Default | `true` |

In the following example, the inventory disables automatic host file management:

```yaml
pgedge:
  vars:
    manage_host_file: false
```
