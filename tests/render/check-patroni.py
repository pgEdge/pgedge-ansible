#!/usr/bin/env python3
"""Render setup_patroni's template offline across the switches that gate it.

Two things this catches that a live run catches late or not at all.

The backup switches: the archive commands appear only where a repository is
configured, and replica creation gains a pgbackrest method only when asked for.
Each combination has to produce valid YAML, and a live run exercises one.

And the facts the template reads out of hostvars. Its HBA rules are built from
the addresses of the zone's proxies and the cluster's backup servers, which are
facts -- they exist only for hosts some play has gathered them on. A playbook
whose plays are all 'pgedge' renders this template against a proxy no play has
touched, and fails partway through the deployment. The last case below is that
playbook, and it is expected to fail.

It also renders the script Debian replicas restore through, which has to
create the configuration directory a restore leaves out.

Ansible's template module turns trim_blocks on, unlike a bare Jinja2
Environment, so a '{%- if %}' that renders cleanly here would not there.
"""

import itertools
import json
import re
import subprocess
import sys

import yaml
from jinja2 import (Environment, FileSystemLoader, StrictUndefined,
                    UndefinedError, select_autoescape)
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO / "roles" / "setup_patroni" / "templates"

# The ultra-ha inventory's shape: two zones of three pgEdge nodes, a proxy and a
# backup server each. The proxy and backup hosts are the point -- an inventory
# without them cannot show the missing-facts failure.
PGEDGE = ["10.0.0.%d" % n for n in (10, 11, 12, 13, 14, 15)]
HAPROXY = ["10.0.0.16", "10.0.0.17"]
BACKUP = ["10.0.0.18", "10.0.0.19"]
ZONE_OF = dict([(h, 1) for h in PGEDGE[:3]] + [(h, 2) for h in PGEDGE[3:]])
ZONE_OF.update({HAPROXY[0]: 1, HAPROXY[1]: 2, BACKUP[0]: 1, BACKUP[1]: 2})

# setup_patroni's role variable naming the Debian pgbackrest replica script.
REPLICA_SCRIPT = "/usr/local/bin/patroni_pgbackrest_replica"

# The Debian replica methods that create /etc/postgresql/<version>/<cluster>,
# keyed by the command each must run. Patroni fails to start a replica whose
# configuration directory has no postgresql.conf.
DEBIAN_CONFIG_METHODS = {
    "pg_clonecluster": "/usr/share/patroni/pg_clonecluster_patroni",
    "pgbackrest": REPLICA_SCRIPT,
}


def env():
    # Autoescaping is declared off rather than left to the default, because it
    # has to be off and the reason is not obvious. What renders here is a
    # Patroni YAML configuration, not markup: HTML-escaping it would turn every
    # & < > ' in a password, an archive command or a restore target into an
    # entity. And Ansible's template module does not autoescape, so switching it
    # on here would render something Ansible never produces, which is the one
    # thing this script exists to rule out.
    #
    # Undefined variables are strict for the same reason: Ansible fails a
    # template that reads one, where Jinja's default renders it as an empty
    # string and lets a context missing a variable pass for a working render.
    e = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                    autoescape=select_autoescape(enabled_extensions=(),
                                                 default_for_string=False,
                                                 default=False),
                    undefined=StrictUndefined,
                    trim_blocks=True, keep_trailing_newline=True)
    for name in ("ipaddr", "ansible.utils.ipaddr"):
        e.filters[name] = lambda v, *a: "10.0.0.9"
    e.filters["bool"] = lambda v: str(v).strip().lower() in ("true", "yes", "on", "1")
    e.filters["regex_replace"] = lambda v, p, r: re.sub(p, r, str(v))
    e.filters["to_json"] = json.dumps
    e.filters["to_nice_yaml"] = lambda v, indent=2: yaml.safe_dump(
        v, default_flow_style=False)
    return e


def hostvars_for(hosts_with_facts):
    """hostvars as Ansible builds them: facts only for hosts a play gathered."""
    hv = {}
    for host in PGEDGE + HAPROXY + BACKUP:
        entry = {"inventory_hostname": host, "zone": ZONE_OF[host]}
        if host in hosts_with_facts:
            entry["ansible_default_ipv4"] = {"address": host}
        hv[host] = entry
    return hv


def context(os_family, backups, replica, hosts_with_facts):
    zone = 1
    in_zone = [h for h in PGEDGE if ZONE_OF[h] == zone]
    return dict(
        ansible_default_ipv4={"address": PGEDGE[0], "netmask": "255.255.255.0"},
        db_names=["demo"], patroni_dcs={"type": "etcd3"},
        default_patroni_dcs_params={"host": "n1:2379", "ttl": 30},
        patroni_scope="17-demo", patroni_namespace="/db/",
        ansible_hostname="n1", inventory_hostname=PGEDGE[0],
        ansible_os_family=os_family,
        backup_repo_configured=backups,
        replica_from_backup=replica, backup_stanza="pgedge-demo-1",
        synchronous_mode="false", synchronous_mode_strict="false",
        pg_port=5432, pg_data="/var/lib/pgsql/17/data",
        pg_config_dir="/var/lib/pgsql/17/data", pg_path="/usr/pgsql-17",
        pg_home="/var/lib/pgsql", pg_version=17, cluster_name="demo", zone=zone,
        patroni_pgbackrest_replica_script=REPLICA_SCRIPT,
        pg_supports_output_plugin_libraries=True,
        spock_exception_behaviour="transdiscard",
        groups={"pgedge": PGEDGE, "haproxy": HAPROXY, "backup": BACKUP},
        hostvars=hostvars_for(hosts_with_facts),
        nodes_in_zone=in_zone,
        proxies_in_zone=[h for h in HAPROXY if ZONE_OF[h] == zone],
        proxy_node="", custom_hba_rules=[], backup_host="",
        pgedge_user="pgedge", db_user="admin", replication_user="replicator",
        backup_user="backrest", db_password="p", replication_password="p")


def debian_config_dir_guaranteed(pg):
    """Whether every Debian replica method Patroni can stop at creates the
    configuration directory.

    Patroni keeps the first method that succeeds, so each one ahead of
    basebackup has to create it, and there has to be at least one: with no
    list at all, Patroni uses basebackup alone. basebackup itself is the last
    resort and creates nothing.
    """
    methods = pg.get("create_replica_methods") or ["basebackup"]
    ahead = methods[:methods.index("basebackup")] if "basebackup" in methods \
        else methods
    return bool(ahead) and all(
        m in DEBIAN_CONFIG_METHODS
        and (pg.get(m) or {}).get("command") == DEBIAN_CONFIG_METHODS[m]
        for m in ahead)


def failed_checks(doc, os_family, backups, replica):
    """The switches each combination has to have produced, and what failed."""
    params = doc["bootstrap"].get("dcs", {}).get("postgresql", {}).get(
        "parameters", {})
    checks = {
        # A recovery restores outside Patroni and hands it a running cluster,
        # so no node ever bootstraps from the repository.
        "bootstrap method":
            doc["bootstrap"].get("method") != "pgbackrest",
        "archive_command":
            ("pgbackrest" in params["archive_command"]) == backups,
        "restore_command present":
            ("restore_command" in params) == backups,
        "pgbackrest replica method":
            ("pgbackrest" in (doc["postgresql"].get(
                "create_replica_methods") or [])) == replica,
        # A Debian restore or clone leaves no postgresql.conf behind unless the
        # method creates one, and the replica then never starts.
        "debian replica config directory":
            os_family != "Debian"
            or debian_config_dir_guaranteed(doc["postgresql"]),
        # Every address the HBA rules name has to be a real one. A host whose
        # facts were missing renders as an empty string or the literal 'None',
        # and Postgres refuses to start on that line.
        "hba addresses resolved":
            all("/32" in line and " None/" not in line
                for line in doc["postgresql"]["pg_hba"]
                if line.startswith("host ") and "127.0.0.1" not in line),
    }
    return [name for name, ok in checks.items() if not ok]


def check_switches(template):
    """Render every combination of the switches that gate the template."""
    everyone = set(PGEDGE + HAPROXY + BACKUP)
    failures = []

    for os_family, backups, replica in itertools.product(
            ["RedHat", "Debian"], [False, True], [False, True]):
        label = f"{os_family} backups={int(backups)} replica={int(replica)}"
        try:
            doc = yaml.safe_load(
                template.render(**context(os_family, backups, replica,
                                          everyone)))
        except Exception as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
            print(f"FAIL     {label}")
            continue

        bad = failed_checks(doc, os_family, backups, replica)
        if bad:
            failures.append(f"{label}: {', '.join(bad)}")
            print(f"FAIL     {label}: {', '.join(bad)}")
        else:
            print(f"ok       {label}")

    return failures


def check_missing_facts(template):
    """A playbook whose plays are all 'pgedge' has no facts for the proxy and
    backup hosts. The template must not render against that, and this asserts
    the failure is still detectable rather than silently producing HBA lines
    with no address in them.
    """
    # Only an undefined variable is the failure this is looking for. Anything
    # else -- a syntax error, a filter this script does not stub -- is the
    # template broken some other way, and passing on it would hide that.
    try:
        template.render(**context("RedHat", True, False, set(PGEDGE)))
    except UndefinedError as exc:
        print("ok       missing proxy/backup facts are rejected "
              f"({type(exc).__name__})")
        return []

    print("FAIL     missing proxy/backup facts rendered anyway")
    return ["a template rendered with no facts for the proxy and backup hosts "
            "produced output instead of failing; a playbook whose plays are all "
            "'pgedge' would emit HBA rules with no addresses in them"]


def check_replica_script(template):
    """The Debian pgbackrest replica script has to be valid shell, restore
    before it touches the configuration directory, and create the cluster's
    configuration only where the restore left none.
    """
    text = template.render(**context("Debian", True, True,
                                     set(PGEDGE + HAPROXY + BACKUP)))
    result = subprocess.run(["sh", "-n"], input=text, text=True,
                            capture_output=True)
    if result.returncode != 0:
        print("FAIL     Debian replica script is not valid shell")
        return [f"pgbackrest_replica.sh.j2: sh -n: {result.stderr.strip()}"]

    restore = text.find("pgbackrest --stanza=pgedge-demo-1 --delta restore")
    guard = text.find("if [ -e '/var/lib/pgsql/17/data/postgresql.conf' ]")
    create = text.find("pg_createcluster -p 5432")
    if not 0 <= restore < guard < create:
        print("FAIL     Debian replica script steps out of order")
        return ["pgbackrest_replica.sh.j2 must restore, then check for "
                "postgresql.conf, then run pg_createcluster"]

    print("ok       Debian replica script")
    return []


def main():
    e = env()
    template = e.get_template("patroni.yml.j2")

    failures = check_switches(template)
    print()
    failures += check_missing_facts(template)
    failures += check_replica_script(e.get_template("pgbackrest_replica.sh.j2"))

    if failures:
        print("\n" + "\n".join(f"  - {f}" for f in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
