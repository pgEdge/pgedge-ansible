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
# Debian
curl -fsS https://apt.pgedge.com/keys/pgedge-rsa.pub | head -1

# RHEL
curl -fsS https://dnf.pgedge.com/keys/pgedge-rsa.pub | head -1
```

Check that the firewall allows HTTPS traffic and retry the `install_repos`
role.

When `repo_url` is set, the role fetches the key from your repository
instead. The failed task names the URL it tried; fetch that URL from the host
with `curl` to confirm your repository serves the key there. If the key lives
elsewhere, set `repo_gpg_key` to its URL.

## Packages Still Come From the pgEdge Servers

**Symptom:** A host with `repo_url` set still downloads packages from
`dnf.pgedge.com` or `apt.pgedge.com`.

**Solution:** Look for another definition that names the pgEdge servers:

```bash
# Debian
grep -rl pgedge.com /etc/apt/sources.list /etc/apt/sources.list.d

# RHEL
grep -rl pgedge.com /etc/yum.repos.d
```

The `install_repos` role replaces only the definition the `pgedge-release`
package created. Remove any definition that someone added by hand, and run
the role again.

## Lock Timeout on Debian

**Symptom:** A "Could not get lock" error occurs on Debian.

**Solution:** Check for other running apt processes:

```bash
ps aux | grep apt
```

The role uses a 300-second timeout. Wait for other package operations to
complete and retry.
