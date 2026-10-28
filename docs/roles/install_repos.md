# install_repos

The `install_repos` role configures official pgEdge package repositories on
target systems. The role enables installation of pgEdge Enterprise Postgres
packages and adds EPEL on RHEL-based systems to satisfy dependencies. The role
can also point hosts at a mirror or caching proxy of your own instead of the
pgEdge servers.

The role performs the following tasks on inventory hosts:

- Install prerequisite packages for repository management.
- Add pgEdge package repositories for the target operating system.
- Configure the EPEL repository on RHEL-based systems.
- Import and verify GPG keys for package signing.
- Update the package cache to make pgEdge packages available.

## Role Dependencies

This role requires the following roles for normal operation:

- `role_config` provides shared configuration variables to the role.
- `init_server` prepares systems before repository installation.

## When to Use

Execute this role on all hosts where you will install pgEdge packages. Run
this role before any package installation roles. The `repo_name` parameter
controls which repository tier to use: `release`, `staging`, or `daily`.

In the following example, the playbook configures repositories on all pgedge
hosts:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Configuration

This role reads the following shared parameters; the
[Cluster Configuration](../configuration/cluster.md) page describes each one:

- `repo_name` selects the repository tier.
- `repo_url` names a mirror or proxy of your own to use in place of the
  pgEdge servers.
- `repo_layout` describes how the repository at `repo_url` arranges its
  contents.
- `repo_gpg_key` overrides where the role fetches the package signing key
  for `repo_url`.

The role handles all other repository configuration automatically based on
the detected operating system.

### Using Your Own Repository

When `repo_url` is set, the role builds the repository definition that the
`pgedge-release` package would install, with every location pointing at
`repo_url`. The role removes the `pgedge-release` package, because an upgrade
of that package would point the host back at the pgEdge servers. The
repository IDs and file names stay the same, so a host can move between the
pgEdge servers and your own repository in either direction by setting or
removing `repo_url` and running the role again.

The following table shows the locations the role uses under `repo_url` for
each layout:

| Layout | RHEL packages | Debian packages | Signing key |
|--------|---------------|-----------------|-------------|
| `upstream` | `<repo_url>/<repo_name>/<major>/RPMS/<arch>/` and `.../RPMS/noarch/` | `<repo_url>/<repo_name>/<codename>` | `<repo_url>/keys/pgedge-rsa.pub` |
| `mirror` | `<repo_url>/el<major>/<arch>/pgedge/` and `.../pgedge-noarch/` | `<repo_url>/apt/<distribution><version>` | `<repo_url>/keys/pgedge-rsa.pub` on RHEL, `<repo_url>/apt/<distribution><version>/pgedge.gpg` on Debian |

In the `upstream` layout, `repo_url` stands for `https://dnf.pgedge.com` on
RHEL hosts and `https://apt.pgedge.com` on Debian hosts; most caching proxies,
such as Artifactory or Nexus remote repositories, keep this layout. An
inventory with hosts of both families sets `repo_url` separately for each
family. In the `mirror` layout, one `repo_url` serves every platform, and
`<distribution><version>` is a name such as `debian12` or `ubuntu24.04`.

In the following example, the playbook installs from a pgEdge mirror on the
internal network:

```yaml
- hosts: pgedge
  collections:
    - pgedge.platform
  vars:
    repo_url: http://mirror.example.com/pgedge
    repo_layout: mirror
  roles:
    - install_repos
```

The `init_server` role refuses an unknown `repo_layout`, a `repo_url` that is
not an `http://`, `https://`, or `file:///` URL, a `repo_gpg_key` without a
`repo_url`, and a `mirror` layout with a `repo_name` other than `release`.

!!! warning "HTTP Repository Trust"
    An `http://` repository does not authenticate the repository or signing-key
    source. An attacker able to intercept the connection can replace both
    before package signature verification. Use `https://`, or set
    `repo_gpg_key` to a separately trusted HTTPS key source when using HTTP.

!!! note "EPEL on RHEL Systems"
    The `repo_url` parameter replaces only the pgEdge repositories. On RHEL
    and Oracle Linux, the role still downloads the EPEL release package from
    `dl.fedoraproject.org`; on Rocky and Alma Linux, the role installs EPEL
    from the distribution's own repositories. A host on an isolated network
    needs those sources available as well.

## How It Works

The role configures package repositories based on the operating system family
detected on each target host.

### Debian Family Setup

On Debian-based systems, the role performs the following steps:

1. Install prerequisite packages including `curl`, `gnupg2`, and
   `lsb-release`.
2. Download and install the pgEdge repository definition package; with
   `repo_url` set, remove that package, install the signing key from
   `repo_url`, and write the repository definition instead.
3. Update the APT package cache to include pgEdge packages.

### RHEL Family Setup

On RHEL-based systems, the role performs the following steps:

1. Install the EPEL repository using the appropriate method for the
   distribution variant.
2. Import the pgEdge GPG key for package verification.
3. Download and install the pgEdge repository definition package; with
   `repo_url` set, remove that package and write the repository definition
   instead.

!!! important "Execution Order"
    Execute this role before any `install_*` roles that install pgEdge
    packages. The role establishes the package sources that all subsequent
    installations need.

!!! warning "EPEL Dependencies"
    RHEL-based systems require EPEL for several Postgres dependencies. The
    role handles EPEL installation automatically but may require subscription
    access on RHEL systems.

!!! note "Network Requirements"
    This role requires outbound HTTPS access to pgEdge repository servers,
    unless `repo_url` names a repository of your own. Ensure firewall rules
    and proxy settings allow this connectivity.

## Usage Examples

In the following example, the playbook configures pgEdge repositories on
pgedge hosts and backup servers:

```yaml
# Install repos on all Postgres nodes
- hosts: pgedge
  collections:
    - pgedge.platform
  roles:
    - install_repos

# Install repos on backup servers
- hosts: backup
  collections:
    - pgedge.platform
  roles:
    - install_repos
```

## Artifacts

This role creates the following repository configuration files on inventory
hosts:

| File | New / Modified | Explanation |
|------|----------------|-------------|
| `/etc/apt/sources.list.d/pgedge.sources` | New | pgEdge repository configuration on Debian systems. |
| `/etc/apt/keyrings/pgedge-rsa.gpg` | New | pgEdge GPG key on Debian systems. |
| `/etc/yum.repos.d/pgedge.repo` | New | pgEdge repository configuration on RHEL systems. |
| `/etc/yum.repos.d/epel.repo` | New | EPEL repository configuration on RHEL systems. |

## Platform-Specific Behavior

On Debian-based systems, the role installs `curl`, `gnupg2`, and `lsb-release`
as prerequisites and uses APT to manage the package cache. On RHEL-based
systems, the EPEL installation method varies by distribution variant and
the role uses DNF for all package operations.

## Idempotency

This role is idempotent and safe to re-run on inventory hosts. The role
delegates package installation to the operating system, which handles existing
packages appropriately.
