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

It also renders the script replicas restore through. It has to refuse a
backup that cannot become a replica of the leader, which is run here against
stand-ins for psql and pgbackrest, and on Debian it has to create the
configuration directory a restore leaves out.

What the template sees as replica_from_backup is not set here. It is derived
from the inventory's patroni_replica_from_backup and backup_repo_configured by
role_config's own expression, read out of role_config's vars, so asking for
replicas from a backup where no repository exists renders as Ansible would
render it -- without the pgbackrest method -- and this also pins that
derivation.

Ansible's template module turns trim_blocks on, unlike a bare Jinja2
Environment, so a '{%- if %}' that renders cleanly here would not there.
"""

import itertools
import json
import re
import os
import subprocess
import sys
import tempfile

import yaml
from jinja2 import (Environment, FileSystemLoader, StrictUndefined,
                    UndefinedError, select_autoescape)
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO / "roles" / "setup_patroni" / "templates"
ROLE_VARS = REPO / "roles" / "role_config" / "vars" / "main.yaml"

# The ultra-ha inventory's shape: two zones of three pgEdge nodes, a proxy and a
# backup server each. The proxy and backup hosts are the point -- an inventory
# without them cannot show the missing-facts failure.
PGEDGE = ["10.0.0.%d" % n for n in (10, 11, 12, 13, 14, 15)]
HAPROXY = ["10.0.0.16", "10.0.0.17"]
BACKUP = ["10.0.0.18", "10.0.0.19"]
ZONE_OF = dict([(h, 1) for h in PGEDGE[:3]] + [(h, 2) for h in PGEDGE[3:]])
ZONE_OF.update({HAPROXY[0]: 1, HAPROXY[1]: 2, BACKUP[0]: 1, BACKUP[1]: 2})

# setup_patroni's role variable naming the pgbackrest replica script.
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


def replica_from_backup(e, requested, backups):
    """role_config's replica_from_backup, evaluated as Ansible would."""
    expr = yaml.safe_load(ROLE_VARS.read_text())["replica_from_backup"]
    return e.from_string(expr).render(patroni_replica_from_backup=requested,
                                      backup_repo_configured=backups)


def context(e, os_family, backups, replica, hosts_with_facts):
    """The template's variables. 'replica' is the inventory's
    patroni_replica_from_backup; what the template sees is derived from it."""
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
        replica_from_backup=replica_from_backup(e, replica, backups),
        backup_stanza="pgedge-demo-1",
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
    """The switches each combination has to have produced, and what failed.

    'replica' is only a request: a replica cannot restore from a repository
    that does not exist, so the pgbackrest method appears only with both.
    """
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
                "create_replica_methods") or [])) == (replica and backups),
        # The script needs the leader's connection string to judge the backup,
        # and Patroni passes it only without no_params.
        "pgbackrest method runs the replica script":
            not (replica and backups)
            or (doc["postgresql"]["pgbackrest"].get("command") == REPLICA_SCRIPT
                and not doc["postgresql"]["pgbackrest"].get("no_params")),
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


def check_switches(e, template):
    """Render every combination of the switches that gate the template."""
    everyone = set(PGEDGE + HAPROXY + BACKUP)
    failures = []

    for os_family, backups, replica in itertools.product(
            ["RedHat", "Debian"], [False, True], [False, True]):
        label = f"{os_family} backups={int(backups)} replica={int(replica)}"
        try:
            doc = yaml.safe_load(
                template.render(**context(e, os_family, backups, replica,
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


def check_missing_facts(e, template):
    """A playbook whose plays are all 'pgedge' has no facts for the proxy and
    backup hosts. The template must not render against that, and this asserts
    the failure is still detectable rather than silently producing HBA lines
    with no address in them.
    """
    # Only an undefined variable is the failure this is looking for. Anything
    # else -- a syntax error, a filter this script does not stub -- is the
    # template broken some other way, and passing on it would hide that.
    try:
        template.render(**context(e, "RedHat", True, False, set(PGEDGE)))
    except UndefinedError as exc:
        print("ok       missing proxy/backup facts are rejected "
              f"({type(exc).__name__})")
        return []

    print("FAIL     missing proxy/backup facts rendered anyway")
    return ["a template rendered with no facts for the proxy and backup hosts "
            "produced output instead of failing; a playbook whose plays are all "
            "'pgedge' would emit HBA rules with no addresses in them"]


def check_replica_script(e, template):
    """The pgbackrest replica script has to be valid shell and judge the backup
    before it restores; on Debian it then creates the cluster's configuration
    only where the restore left none.
    """
    failures = []
    for os_family in ("RedHat", "Debian"):
        text = template.render(**context(e, os_family, True, True,
                                            set(PGEDGE + HAPROXY + BACKUP)))
        result = subprocess.run(["sh", "-n"], input=text, text=True,
                                capture_output=True)
        if result.returncode != 0:
            print(f"FAIL     {os_family} replica script is not valid shell")
            failures.append(f"pgbackrest_replica.sh.j2 ({os_family}): sh -n: "
                            f"{result.stderr.strip()}")
            continue

        judge = text.find("python3 - '/usr/pgsql-17/bin/psql'")
        restore = text.find("pgbackrest --stanza=pgedge-demo-1 --delta restore")
        guard = text.find("if [ -e '/var/lib/pgsql/17/data/postgresql.conf' ]")
        create = text.find("pg_createcluster -p 5432")
        if os_family == "Debian":
            ordered = 0 <= judge < restore < guard < create
            want = "judge the backup, restore, check for postgresql.conf, " \
                   "then run pg_createcluster"
        else:
            ordered = 0 <= judge < restore and guard < 0 and create < 0
            want = "judge the backup, then restore, and nothing more"
        if not ordered:
            print(f"FAIL     {os_family} replica script steps out of order")
            failures.append(f"pgbackrest_replica.sh.j2 ({os_family}) must "
                            f"{want}")
            continue
        print(f"ok       {os_family} replica script")
    return failures


# Stand-ins the replica script runs instead of the real psql and pgbackrest.
# psql answers the two replication commands from the environment; pgbackrest
# prints the repository's info and records that a restore ran.
STUB_PSQL = """#!/bin/sh
for arg in "$@"; do last=$arg; done
case "$last" in
    IDENTIFY_SYSTEM) echo "$STUB_SYSID|$STUB_TLI|0/9000000|" ;;
    TIMELINE_HISTORY*) printf '%08X.history|%b' "$STUB_TLI" "$STUB_HISTORY" ;;
    *) exit 1 ;;
esac
"""
STUB_PGBACKREST = """#!/bin/sh
case "$*" in
    *info*) printf '%s\\n' "$STUB_INFO" ;;
    *restore*) touch "$STUB_RESTORED" ;;
esac
"""

SYSID = "7400000000000000001"


def repo_info(*backups):
    """pgbackrest info for one stanza: (system id, timeline, stop lsn)."""
    dbs = {sysid: i + 1 for i, sysid in
           enumerate(dict.fromkeys(b[0] for b in backups))}
    return json.dumps([{
        "name": "pgedge-demo-1",
        "db": [{"id": i, "system-id": int(sysid)} for sysid, i in dbs.items()],
        "backup": [{"label": f"backup{n}",
                    "timestamp": {"stop": 1000 + n},
                    "database": {"id": dbs[sysid]},
                    "archive": {"start": f"{tli:08X}000000000000000A"},
                    "lsn": {"stop": stop}}
                   for n, (sysid, tli, stop) in enumerate(backups)],
    }])


# Each case: what it is, the repository, the leader's timeline and history, and
# whether the script should restore.
DECISIONS = [
    ("backup on the leader's timeline",
     repo_info((SYSID, 1, "0/5000000")), 1, "", True),
    ("backup before the leader's branch point",
     repo_info((SYSID, 1, "0/5000000")), 2,
     "1\\t0/7000000\\tno recovery target specified\\n", True),
    ("backup ending at the branch point",
     repo_info((SYSID, 1, "0/7000000")), 2, "1\\t0/7000000\\treason\\n", True),
    ("backup on an ancestor two timelines back",
     repo_info((SYSID, 1, "0/5000000")), 3,
     "1\\t0/7000000\\tr\\n2\\t0/8000000\\tr\\n", True),
    ("backup past the leader's branch point (PITR)",
     repo_info((SYSID, 1, "1/0")), 2, "1\\t0/FFFFFFFF\\tr\\n", False),
    ("backup on a timeline the leader abandoned",
     repo_info((SYSID, 1, "0/5000000"), (SYSID, 3, "0/9000000")), 4,
     "1\\t0/7000000\\tr\\n2\\t0/8000000\\tr\\n", False),
    ("only the newest backup counts",
     repo_info((SYSID, 1, "0/5000000"), (SYSID, 1, "0/8000000")), 2,
     "1\\t0/7000000\\tr\\n", False),
    ("backup of another cluster",
     repo_info(("7400000000000000002", 1, "0/5000000")), 1, "", False),
    ("repository with no backup",
     repo_info(), 1, "", False),
    ("timeline 1 leader, newer backup timeline",
     repo_info((SYSID, 2, "0/5000000")), 1, "", False),
]


def check_replica_decision(e, template):
    """Run the replica script against each repository and leader the cases
    describe, and check it restores exactly the backups that can follow it.
    """
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "bin").mkdir()
        for name, body in (("psql", STUB_PSQL), ("pgbackrest", STUB_PGBACKREST)):
            stub = tmp / "bin" / name
            stub.write_text(body)
            stub.chmod(0o755)
        ctx = context(e, "RedHat", True, True, set(PGEDGE + HAPROXY + BACKUP))
        ctx["pg_path"] = str(tmp)
        script = tmp / "replica.sh"
        script.write_text(template.render(**ctx))

        for label, info, tli, history, restores in DECISIONS:
            marker = tmp / "restored"
            marker.unlink(missing_ok=True)
            run_env = dict(os.environ, PATH=f"{tmp / 'bin'}:{os.environ['PATH']}",
                           STUB_SYSID=SYSID, STUB_TLI=str(tli),
                           STUB_HISTORY=history, STUB_INFO=info,
                           STUB_RESTORED=str(marker))
            result = subprocess.run(
                ["sh", str(script), "--keep_data=True", "--scope=17-demo",
                 "--role=replica", "--datadir=/var/lib/pgsql/17/data",
                 "--connstring=host=10.0.0.10 port=5432 user=replicator"],
                env=run_env, capture_output=True, text=True)
            restored = marker.exists()
            ok = restored == restores and (result.returncode == 0) == restores
            print(f"{'ok' if ok else 'FAIL':<9}replica decision: {label}")
            if not ok:
                failures.append(
                    f"replica decision '{label}': expected "
                    f"{'a restore' if restores else 'a refusal'}, got rc "
                    f"{result.returncode}, restored={restored}: "
                    f"{result.stderr.strip()}")
    return failures


def main():
    e = env()
    template = e.get_template("patroni.yml.j2")

    failures = check_switches(e, template)
    print()
    failures += check_missing_facts(e, template)
    failures += check_replica_script(
        e, e.get_template("pgbackrest_replica.sh.j2"))
    failures += check_replica_decision(
        e, e.get_template("pgbackrest_replica.sh.j2"))

    if failures:
        print("\n" + "\n".join(f"  - {f}" for f in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
