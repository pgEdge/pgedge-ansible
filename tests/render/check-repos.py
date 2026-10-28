#!/usr/bin/env python3
"""Render install_repos' repository definitions offline and compare them.

With repo_url set, install_repos writes the repository definition pgEdge's
pgedge-release package would have, pointed at the site's repository instead.
Nothing in a container run can tell whether that definition is the package's
equivalent: a cluster installs as long as some definition works. So each case
here renders the definition for one platform and compares it with the one it
must match, kept in expected/:

  pgedge-release.*  what the package itself installs. repo_url naming pgEdge's
                    own servers in the 'upstream' layout must reproduce it
                    exactly, and a proxy in that layout must differ from it
                    only by its address and tier.
  mirror-layout.*   the client files a mirror built by pgEdge's proposed
                    mirror procedure offers. A 'mirror' layout repository
                    must point at the same places.

Should pgEdge change either, the expected files are what to update, from the
package or the mirror procedure, and this check then says what install_repos
must change to match.

The renders run the role's own templates and variables through Ansible, the
way the role does on a host, with the facts each platform would report.
"""

import configparser
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXPECTED = HERE / "expected"
ROLE = REPO / "roles" / "install_repos"
DEFAULTS = REPO / "roles" / "role_config" / "defaults" / "main.yaml"

PLAYBOOK = """\
- hosts: all
  gather_facts: false
  tasks:
  - include_vars: {role}/vars/main.yaml
  - template:
      src: {role}/templates/pgedge.repo.j2
      dest: "{{{{ out }}}}/{{{{ inventory_hostname }}}}.repo"
    when: ansible_os_family == 'RedHat'
  - template:
      src: {role}/templates/pgedge.sources.j2
      dest: "{{{{ out }}}}/{{{{ inventory_hostname }}}}.sources"
    when: ansible_os_family == 'Debian'
  - copy:
      content: "{{{{ repo_key_url }}}}"
      dest: "{{{{ out }}}}/{{{{ inventory_hostname }}}}.key"
"""


def facts(family, distribution, version, release):
    return {"ansible_os_family": family,
            "ansible_distribution": distribution,
            "ansible_distribution_version": version,
            "ansible_distribution_major_version": version.split(".")[0],
            "ansible_distribution_release": release}


ROCKY9 = facts("RedHat", "Rocky", "9.6", "Blue Onyx")
ALMA10 = facts("RedHat", "AlmaLinux", "10.0", "Purple Lion")
DEBIAN12 = facts("Debian", "Debian", "12", "bookworm")
DEBIAN13 = facts("Debian", "Debian", "13", "trixie")
UBUNTU2204 = facts("Debian", "Ubuntu", "22.04", "jammy")
UBUNTU2404 = facts("Debian", "Ubuntu", "24.04", "noble")

DNF = "https://dnf.pgedge.com"
APT = "https://apt.pgedge.com"
MIRROR = "http://mirror.example.internal/pgedge"
PROXY = "https://artifacts.example.internal/pgedge-dnf"

# The fields compared between two definitions. pgedge-release's own are
# compared in full; the mirror's, only for where they point.
ALL = None
DNF_LOCATIONS = ("baseurl", "enabled", "gpgcheck", "gpgkey")
APT_LOCATIONS = ("Types", "URIs", "Suites", "Components")

# (name, facts, inventory vars, expected file, [(placeholder, value)],
#  fields compared, the key's URL)
CASES = [
    ("pgEdge's own servers on EL 9", ROCKY9,
     {"repo_url": DNF},
     "pgedge-release.repo", [("OS_VERSION", "9"), ("OS_ARCH", "$basearch")],
     ALL, f"{DNF}/keys/pgedge-rsa.pub"),
    ("pgEdge's own servers on EL 10", ALMA10,
     {"repo_url": DNF + "/"},
     "pgedge-release.repo", [("OS_VERSION", "10"), ("OS_ARCH", "$basearch")],
     ALL, f"{DNF}/keys/pgedge-rsa.pub"),
    ("pgEdge's own servers on Debian 12", DEBIAN12,
     {"repo_url": APT},
     "pgedge-release.sources", [("CODENAME", "bookworm")],
     ALL, f"{APT}/keys/pgedge-rsa.pub"),
    ("pgEdge's own servers on Ubuntu 24.04", UBUNTU2404,
     {"repo_url": APT},
     "pgedge-release.sources", [("CODENAME", "noble")],
     ALL, f"{APT}/keys/pgedge-rsa.pub"),
    ("a proxy of the staging tier on EL 9", ROCKY9,
     {"repo_url": PROXY, "repo_name": "staging"},
     "pgedge-release.repo",
     [(f"{DNF}/release/", f"{PROXY}/staging/"), (DNF, PROXY),
      ("OS_VERSION", "9"), ("OS_ARCH", "$basearch")],
     ALL, f"{PROXY}/keys/pgedge-rsa.pub"),
    ("a proxy of the daily tier on Ubuntu 24.04", UBUNTU2404,
     {"repo_url": "https://artifacts.example.internal/pgedge-apt",
      "repo_name": "daily"},
     "pgedge-release.sources",
     [(f"{APT}/release/", "https://artifacts.example.internal/pgedge-apt/daily/"),
      ("CODENAME", "noble")],
     ALL, "https://artifacts.example.internal/pgedge-apt/keys/pgedge-rsa.pub"),
    ("a proxy with a key of the site's own on Debian 13", DEBIAN13,
     {"repo_url": "http://10.0.0.40:8080/apt//",
      "repo_gpg_key": "https://keys.example.internal/pgedge.asc"},
     "pgedge-release.sources",
     [(APT, "http://10.0.0.40:8080/apt"), ("CODENAME", "trixie")],
     ALL, "https://keys.example.internal/pgedge.asc"),
    ("a tier repo_name does not know falls back to release", ROCKY9,
     {"repo_url": DNF, "repo_name": "download"},
     "pgedge-release.repo", [("OS_VERSION", "9"), ("OS_ARCH", "$basearch")],
     ALL, f"{DNF}/keys/pgedge-rsa.pub"),
    ("the mirror on EL 9", ROCKY9,
     {"repo_url": MIRROR + "/", "repo_layout": "mirror"},
     "mirror-layout.repo", [("MIRROR_URL", MIRROR), ("PLATFORM", "el9")],
     DNF_LOCATIONS, f"{MIRROR}/keys/pgedge-rsa.pub"),
    ("the mirror on EL 10", ALMA10,
     {"repo_url": MIRROR, "repo_layout": "mirror"},
     "mirror-layout.repo", [("MIRROR_URL", MIRROR), ("PLATFORM", "el10")],
     DNF_LOCATIONS, f"{MIRROR}/keys/pgedge-rsa.pub"),
    ("the mirror on Debian 13", DEBIAN13,
     {"repo_url": MIRROR, "repo_layout": "mirror"},
     "mirror-layout.sources",
     [("MIRROR_URL", MIRROR), ("PLATFORM", "debian13"),
      ("CODENAME", "trixie")],
     APT_LOCATIONS, f"{MIRROR}/apt/debian13/pgedge.gpg"),
    ("the mirror on Ubuntu 22.04", UBUNTU2204,
     {"repo_url": MIRROR, "repo_layout": "mirror"},
     "mirror-layout.sources",
     [("MIRROR_URL", MIRROR), ("PLATFORM", "ubuntu22.04"),
      ("CODENAME", "jammy")],
     APT_LOCATIONS, f"{MIRROR}/apt/ubuntu22.04/pgedge.gpg"),
]


def parse_repo(text):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(text)
    return {s: dict(parser[s]) for s in parser.sections()}


def parse_sources(text):
    fields = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return {"": fields}


def compare(rendered, expected, fields):
    problems = []
    if rendered.keys() != expected.keys():
        problems.append(f"defines {sorted(rendered)}, "
                        f"expected {sorted(expected)}")
    for section in rendered.keys() & expected.keys():
        keys = fields or rendered[section].keys() | expected[section].keys()
        for key in sorted(keys):
            got = rendered[section].get(key)
            want = expected[section].get(key)
            if got != want:
                where = f"[{section}] " if section else ""
                problems.append(f"{where}{key} is {got!r}, expected {want!r}")
    return problems


def render(workdir):
    defaults = yaml.safe_load(DEFAULTS.read_text())
    base = {k: v for k, v in defaults.items() if k.startswith("repo_")}
    hosts = {}
    for i, (_, platform, given, *_rest) in enumerate(CASES):
        hosts[f"case{i}"] = {**base, **platform, **given,
                             "ansible_connection": "local",
                             "ansible_python_interpreter": sys.executable,
                             "out": str(workdir)}
    inventory = workdir / "inventory.json"
    inventory.write_text(json.dumps({"all": {"hosts": hosts}}))
    (workdir / "play.yml").write_text(PLAYBOOK.format(role=ROLE))
    (workdir / "ansible.cfg").write_text("[defaults]\n")
    env = dict(os.environ,
               ANSIBLE_CONFIG=str(workdir / "ansible.cfg"),
               ANSIBLE_NOCOLOR="1",
               ANSIBLE_LOCALHOST_WARNING="0")
    result = subprocess.run(
        ["ansible-playbook", "-i", str(inventory), str(workdir / "play.yml")],
        env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout + result.stderr)
        sys.exit("The templates could not be rendered.")


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        render(workdir)
        for i, (name, _, _, golden, subs, fields, key) in enumerate(CASES):
            suffix = pathlib.Path(golden).suffix
            parse = parse_repo if suffix == ".repo" else parse_sources
            text = (EXPECTED / golden).read_text()
            for placeholder, value in subs:
                text = text.replace(placeholder, value)
            rendered = (workdir / f"case{i}{suffix}").read_text()
            problems = compare(parse(rendered), parse(text), fields)
            got_key = (workdir / f"case{i}.key").read_text()
            if got_key != key:
                problems.append(f"the key is fetched from {got_key!r}, "
                                f"expected {key!r}")
            if problems:
                failures += 1
                print(f"WRONG    {name}")
                for problem in problems:
                    print(f"  {problem}")
            else:
                print(f"ok       {name}")

    if failures:
        print(f"\n{failures} definition(s) differ from the one to match.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
