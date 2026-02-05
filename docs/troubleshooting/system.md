# Solving System-Level Issues

System-level configuration issues can derail even well-planned deployments,
particularly when dealing with security enhancements like SELinux, SSH key
management, or host naming resolution. These problems frequently manifest
during automated provisioning when Ansible attempts to reconfigure fundamental
system components that may be customized or locked down for security reasons.

Issues with SSH connectivity, host resolution, or permission requirements for
automated reboots can leave systems in inconsistent states as well. This
section covers troubleshooting approaches for system-wide configuration
challenges, helping you maintain secure environments while ensuring Ansible can
successfully perform required system modifications.

## SELinux Reboot Issues

**Symptom:** The system fails to come back online after SELinux configuration.

**Solution:**

- Verify that the system maintains SSH connectivity through reboots.
- Check that the firewall rules allow SSH connections.
- Increase the wait timeout in the Ansible configuration.
- Manually check the system status after a reboot completes.

## SSH Key Problems

**Symptom:** The role failed to generate or distribute SSH keys properly.

**Solution:**

- Verify that the `postgres` user exists on all target hosts.
- Check that the `.ssh` directory has permissions set to 700.
- Check that the private keys have permissions set to 600.
- Check that the public keys have permissions set to 644.
- Ensure that Ansible has write access to the `host-keys` directory.

## Host File Issues

**Symptom:** Nodes fail to resolve each other's hostnames.

**Solution:**

- Verify that `/etc/hosts` contains entries for all cluster nodes.
- Check that your inventory sets `manage_host_file` to `true`.
- Ensure that the inventory contains correct hostnames and IP addresses.
- Test name resolution by running `ping hostname` for each cluster node.
