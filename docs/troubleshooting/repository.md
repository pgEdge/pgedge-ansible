# Repository Issues

This page covers issues that prevent software installation.

## Repository Package Not Found

**Symptom:** Package installation fails with a "package not found" error
after `install_repos` runs.

**Solution:** Refresh the package cache and search for the package:

```bash
# Debian
sudo apt update && apt-cache search pgedge-enterprise

# RHEL
sudo dnf makecache && dnf search pgedge-enterprise
```

Verify that the correct repository configuration exists:

```bash
# Debian
cat /etc/apt/sources.list.d/pgedge.sources

# RHEL
cat /etc/yum.repos.d/pgedge.repo
```

## GPG Key Import Fails

**Symptom:** The repository key import task fails.

**Solution:** Verify network access to the pgEdge repository:

```bash
curl -s https://pgedge-downstream.s3.amazonaws.com/REPO/ubuntu/pgdg/jammy.pub
```

Check that the firewall allows HTTPS traffic and retry the `install_repos`
role.

## Lock Timeout on Debian

**Symptom:** A "Could not get lock" error occurs on Debian.

**Solution:** Check for other running apt processes:

```bash
ps aux | grep apt
```

The role uses a 300-second timeout. Wait for other package operations to
complete and retry.
