# System Configuration

These parameters affect the base operating system configuration on inventory
hosts. The collection supports Debian and RHEL variant Linux systems including
Debian 12, Rocky Linux 9, and similar distributions.

## debug_pgedge

- Type: Boolean
- Default: `true`
- Description: This parameter configures kernel settings to retain core files
  from process crashes for debugging purposes. When enabled, the collection
  configures `systemd-coredump`, sets kernel parameters to allow unlimited
  core dump sizes, and configures PAM limits.

In the following example, the inventory disables core file retention:

```yaml
pgedge:
  vars:
    debug_pgedge: false
```

## disable_selinux

- Type: Boolean
- Default: `true`
- Description: This parameter controls whether SELinux remains enabled on
  RHEL-based inventory hosts. When `true`, the collection disables SELinux
  and reboots the system to apply the change. This parameter has no effect on
  Debian-based systems.

In the following example, the inventory keeps SELinux enabled:

```yaml
pgedge:
  vars:
    disable_selinux: false
```

!!! warning "Reboot Required"
    Changing the SELinux enforcement state requires a system reboot. The
    `init_server` role handles the reboot automatically but only when the
    state requires a change.

## manage_host_file

- Type: Boolean
- Default: `true`
- Description: This parameter controls automatic management of the
  `/etc/hosts` file on all cluster nodes. When enabled, the collection adds
  all cluster hosts to the hosts file on every node so nodes can resolve each
  other by hostname. Disable this parameter when using external DNS or when
  inventory hostnames are IP addresses.

In the following example, the inventory disables automatic host file
management:

```yaml
pgedge:
  vars:
    manage_host_file: false
```
