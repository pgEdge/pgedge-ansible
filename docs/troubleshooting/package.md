# Solving Package Installation Issues

Package installation problems often manifest after repository configuration but
before actual service deployment. These problems may result in confusing error
states where the repository exists but packages remain uninstallable. The
issues typically arise from stale caches, incorrect repository selections, or
version mismatches between available and requested packages.

Dependency conflicts with existing Postgres installations or system cron
services further complicate the installation landscape. This section provides
systematic approaches to diagnose package availability issues, verify
repository connections, and resolve common installation conflicts that prevent
successful deployment of pgEdge components.

## Package Not Found

**Symptom:** Package installation fails with a "package not found" error.

**Solution:**

Check the following items to resolve the issue:

- Verify the `install_repos` role completed successfully.
- Refresh the package cache with the following commands:

```bash
# Debian/Ubuntu
sudo apt update
apt-cache search pgedge-enterprise

# RHEL/Rocky
sudo dnf makecache
dnf search pgedge-enterprise
```

- Verify the system has the correct repository configured:

```bash
# Debian/Ubuntu
cat /etc/apt/sources.list.d/pgedge.sources

# RHEL/Rocky
cat /etc/yum.repos.d/pgedge.repo
```

## Package Installation Failures

**Symptom:** Package installation fails with repository errors

**Solution:**

- Verify that the target host has internet connectivity.
- Check that the repository configuration is correct.
- Update the package cache manually using the appropriate command for your
  distribution.

On Debian systems, run the following command to update the package cache:

```bash
apt update
```

On RHEL systems, run the following command to update the package cache:

```bash
dnf makecache
```

## Version Mismatch

**Symptom:** The installer deployed the wrong Postgres version.

**Solution:**

Check the following items to resolve the issue:

- Verify the inventory sets the `pg_version` variable correctly.
- Check the available package versions with the following commands:

```bash
# Debian/Ubuntu
apt-cache policy pgedge-enterprise-all-17

# RHEL/Rocky
dnf list pgedge-enterprise-all_17
```

- Ensure the version-specific package exists in the repository.

## Dependency Conflicts

**Symptom:** Dependency conflicts cause package installation to fail.

**Solution:**

Check for conflicting Postgres installations:

```bash
# List installed Postgres packages
dpkg -l | grep postgres  # Debian/Ubuntu
rpm -qa | grep postgres  # RHEL/Rocky
```

Remove conflicting packages if safe:

```bash
# Debian/Ubuntu
sudo apt remove [conflicting packages]

# RHEL/Rocky
sudo dnf remove [conflicting packages]
```

## Network Timeouts

**Symptom:** Package downloads timeout or fail intermittently.

**Solution:** The roles retry downloads 5 times with 20-second delays by
default. Check the following items to resolve persistent issues:

- Check network connectivity to the repository servers.
- Verify the repository servers are accessible from the target network.
- Consider using a local package mirror for improved reliability.

## Lock Timeout on Debian

**Symptom:** A "Could not get lock" error occurs on Debian or Ubuntu.

**Solution:**

Check for hung apt processes:

```bash
ps aux | grep apt
```

Wait for other package operations to complete; the role uses a 300-second
timeout.

## Cron Package Conflicts

**Symptom:** Cron installation fails due to conflicts.

**Solution:**

Check for existing cron installations:

```bash
# Debian/Ubuntu
dpkg -l '*cron*'

# RHEL/Rocky
rpm -qa | grep cron
```

Remove conflicting packages if safe:

```bash
# RHEL only (if anacron conflicts)
sudo dnf remove cronie-anacron
sudo dnf install cronie
```
