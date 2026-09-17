#!/usr/bin/env python3
"""Render setup_patroni's template offline across the switches that gate it.

Two things this catches that a live run catches late or not at all.

The recovery switches: bootstrap.method becomes a PgBackRest restore for the one
node a recovery names, the archive commands appear only where a repository is
configured, and replica creation gains a pgbackrest method only when asked for.
Each combination has to produce valid YAML, and a live run exercises one.

And the facts the template reads out of hostvars. Its HBA rules are built from
the addresses of the zone's proxies and the cluster's backup servers, which are
facts -- they exist only for hosts some play has gathered them on. A playbook
whose plays are all 'pgedge' renders this template against a proxy no play has
touched, and fails on the restored node after the cluster has been erased. The
last case below is that playbook, and it is expected to fail.

Ansible's template module turns trim_blocks on, unlike a bare Jinja2
Environment, so a '{%- if %}' that renders cleanly here would not there.
"""

import itertools
import json
import re
import sys

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
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


def env():
    # Autoescaping is declared off rather than left to the default, because it
    # has to be off and the reason is not obvious. What renders here is a
    # Patroni YAML configuration, not markup: HTML-escaping it would turn every
    # & < > ' in a password, an archive command or a restore target into an
    # entity. And Ansible's template module does not autoescape, so switching it
    # on here would render something Ansible never produces, which is the one
    # thing this script exists to rule out.
    e = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                    autoescape=select_autoescape(enabled_extensions=(),
                                                 default_for_string=False,
                                                 default=False),
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


def context(os_family, restore, backups, replica, hosts_with_facts):
    zone = 1
    in_zone = [h for h in PGEDGE if ZONE_OF[h] == zone]
    return dict(
        ansible_default_ipv4={"address": PGEDGE[0], "netmask": "255.255.255.0"},
        db_names=["demo"], patroni_dcs={"type": "etcd3"},
        default_patroni_dcs_params={"host": "n1:2379", "ttl": 30},
        patroni_scope="17-demo", patroni_namespace="/db/",
        ansible_hostname="n1", inventory_hostname=PGEDGE[0],
        ansible_os_family=os_family,
        restore_on_bootstrap=restore, backup_repo_configured=backups,
        replica_from_backup=replica, backup_stanza="pgedge-demo-1",
        recovery_restore_command=(
            'pgbackrest --stanza=pgedge-demo-1 --delta --type=time '
            '--target="2026-09-15 14:30:00+00" --target-action=promote restore'),
        synchronous_mode="false", synchronous_mode_strict="false",
        pg_port=5432, pg_data="/var/lib/pgsql/17/data",
        pg_config_dir="/var/lib/pgsql/17/data", pg_path="/usr/pgsql-17",
        pg_home="/var/lib/pgsql", pg_version=17, cluster_name="demo", zone=zone,
        pg_supports_output_plugin_libraries=True,
        spock_exception_behaviour="transdiscard",
        groups={"pgedge": PGEDGE, "haproxy": HAPROXY, "backup": BACKUP},
        hostvars=hostvars_for(hosts_with_facts),
        nodes_in_zone=in_zone,
        proxies_in_zone=[h for h in HAPROXY if ZONE_OF[h] == zone],
        proxy_node="", custom_hba_rules=[], backup_host="",
        pgedge_user="pgedge", db_user="admin", replication_user="replicator",
        backup_user="backrest", db_password="p", replication_password="p")


def failed_checks(doc, restore, backups, replica):
    """The switches each combination has to have produced, and what failed."""
    params = doc["bootstrap"].get("dcs", {}).get("postgresql", {}).get(
        "parameters", {})
    checks = {
        "bootstrap method":
            (doc["bootstrap"].get("method") == "pgbackrest") == restore,
        "archive_command":
            ("pgbackrest" in params["archive_command"]) == backups,
        "restore_command present":
            ("restore_command" in params) == backups,
        "pgbackrest replica method":
            ("pgbackrest" in (doc["postgresql"].get(
                "create_replica_methods") or [])) == replica,
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

    for os_family, restore, backups, replica in itertools.product(
            ["RedHat", "Debian"], [False, True], [False, True], [False, True]):
        if restore and not backups:
            continue  # restore_on_bootstrap already requires a repository
        label = (f"{os_family} restore={int(restore)} backups={int(backups)} "
                 f"replica={int(replica)}")
        try:
            doc = yaml.safe_load(
                template.render(**context(os_family, restore, backups,
                                          replica, everyone)))
        except Exception as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
            print(f"FAIL     {label}")
            continue

        bad = failed_checks(doc, restore, backups, replica)
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
    try:
        template.render(**context("RedHat", True, True, False, set(PGEDGE)))
    except Exception as exc:
        print("ok       missing proxy/backup facts are rejected "
              f"({type(exc).__name__})")
        return []

    print("FAIL     missing proxy/backup facts rendered anyway")
    return ["a template rendered with no facts for the proxy and backup hosts "
            "produced output instead of failing; a playbook whose plays are all "
            "'pgedge' would emit HBA rules with no addresses in them"]


def main():
    template = env().get_template("patroni.yml.j2")

    failures = check_switches(template)
    print()
    failures += check_missing_facts(template)

    if failures:
        print("\n" + "\n".join(f"  - {f}" for f in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
