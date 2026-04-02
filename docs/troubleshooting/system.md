# System Configuration

This page covers host-level configuration issues.

## SELinux Causes Service Failure

**Symptom:** Services fail on RHEL after deployment due to SELinux denials.

**Solution:** Check SELinux audit logs for denials:

```bash
sudo ausearch -m AVC -ts recent
```

The `init_server` role sets `disable_selinux: true` by default. If you
changed this setting, review the audit logs and create the appropriate
SELinux policy. A system reboot may be required after disabling SELinux.

## SSH Key Problems

**Symptom:** PgBackRest SSH backup fails because of key authentication
errors.

**Solution:** Verify that the `postgres` OS user's SSH key exists and has
correct permissions:

```bash
sudo -u postgres ls -la ~/.ssh/
```

Verify that the public key appears in the `authorized_keys` file on the
backup server:

```bash
sudo -u backup-user cat ~/.ssh/authorized_keys
```

## Hostname Resolution Fails

**Symptom:** Nodes cannot reach each other by hostname.

**Solution:** Verify that `manage_host_file` is `true` so the collection
populates `/etc/hosts` on every node. If external DNS handles resolution,
confirm that each hostname resolves correctly:

```bash
nslookup node1.example.com
```
