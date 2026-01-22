# Solving pgEdge Software Repository Issues

Configuring package repositories correctly is crucial for successful pgEdge
deployments, as the system relies on accessing pgEdge-maintained repositories
to install required software components. Network connectivity issues, firewall
rules, or misconfigured repository endpoints frequently cause installation
failures that prevent the automation from proceeding.

This section guides you through diagnosing and resolving repository-related
problems, from basic connectivity tests to advanced troubleshooting for proxy
environments and GPG key management. Proper repository configuration ensures
the system can download and install all required packages without interrupting
cluster provisioning.

## Repository Package Download Fails

**Symptom:** The role failed to download repository package from pgEdge URLs.

**Solution:**

Check the following items to resolve the issue:

- Verify internet connectivity from target hosts.
- Check that firewall rules allow HTTPS traffic on port 443 outbound.
- Verify DNS resolution for `apt.pgedge.com` or `dnf.pgedge.com`.
- Check proxy settings if the environment uses an HTTP proxy.

Test connectivity with the following commands:

```bash
curl -I https://apt.pgedge.com/repodeb/pgedge-release_latest_all.deb
curl -I https://dnf.pgedge.com/reporpm/pgedge-release-latest.noarch.rpm
```

## GPG Key Import Fails

**Symptom:** GPG key verification errors occur during repository installation.

**Solution:**

Check the following items to resolve the issue:

- Verify the GPG key URL is accessible from the target host.
- Check that the system time is correct since time affects key validity.
- Manually import the key using the following commands:

```bash
# Debian/Ubuntu
curl https://apt.pgedge.com/keys/pgedge.pub | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/pgedge.gpg

# RHEL/Rocky
sudo rpm --import https://dnf.pgedge.com/keys/pgedge.pub
```

## Package Cache Not Updated

**Symptom:** The package manager cannot find pgEdge packages after repository
installation.

**Solution:**

Manually update the package cache with the following commands:

```bash
# Debian/Ubuntu
sudo apt update

# RHEL/Rocky
sudo dnf makecache
```

Verify the system has the repository enabled:

```bash
# Debian/Ubuntu
apt-cache policy | grep pgedge

# RHEL/Rocky
dnf repolist | grep pgedge
```
