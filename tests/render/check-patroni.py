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

The Postgres parameters are derived the same way: pg_effective_parameters and
the layers beneath it are role_config's expressions, evaluated here against an
inventory's pg_parameters, so a case with parameters of its own checks the
layering as well as the rendering. The worker and slot defaults among them are
sized from the shape of the cluster, and are checked against the worked
examples in Spock's sizing guide across clusters of other shapes.

So are the HBA rules for the hosts of other components: pg_required_hba_rules
is role_config's expression, evaluated against the inventory's groups, so the
AI DBA Workbench case checks that the rule comes from role_config as well as
how the template writes it.

Ansible's template module turns trim_blocks on, unlike a bare Jinja2
Environment, so a '{%- if %}' that renders cleanly here would not there.
"""

import itertools
import json
from jinja2.nativetypes import NativeEnvironment
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
AI_DBA_WORKBENCH = ["10.0.0.33"]
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


# role_config's parameter layers, in the order each reads the one before. The
# sizing layers read the cluster's shape and max_parallel_workers, and
# pg_default_parameters is built from them.
PARAMETER_LAYERS = ("pg_coldfront_parameters",
                    "pg_coldfront_default_parameters",
                    "pg_coldfront_preload_libraries",
                    "pg_user_parameters",
                    "zone_list", "nodes_in_zone", "pg_spock_nodes",
                    "pg_connectable_dbs", "pg_spock_subscriptions",
                    "pg_physical_standbys", "pg_parallel_workers",
                    "pg_worker_processes", "pg_replication_slots",
                    "pg_sized_parameters", "pg_default_parameters",
                    "pg_user_preload_libraries",
                    "pg_preload_libraries", "pg_required_parameters",
                    "pg_merged_parameters", "pg_effective_parameters")


def ansible_filters(e):
    """The Ansible filters role_config's parameter expressions use."""
    def combine(*dicts):
        out = {}
        for d in dicts:
            out.update(d)
        return out
    e.filters["combine"] = combine
    e.filters["dict2items"] = lambda d: [{"key": k, "value": v}
                                         for k, v in d.items()]
    e.filters["items2dict"] = lambda items: {i["key"]: i["value"]
                                             for i in items}
    e.filters["zip"] = lambda a, *b: list(zip(a, *b))
    e.filters["product"] = lambda a, *b: list(itertools.product(a, *b))
    e.filters["difference"] = lambda a, b: [x for x in a if x not in list(b)]
    e.filters["intersect"] = lambda a, b: [x for x in a if x in list(b)]
    # Ansible's unique returns a list, where Jinja's returns a generator.
    e.filters["unique"] = lambda a: list(dict.fromkeys(a))
    e.filters["extract"] = lambda key, container: container[key]
    e.filters["bool"] = lambda v: str(v).strip().lower() in (
        "true", "yes", "on", "1")
    return e


def cluster(zones, members=1, db_names=("demo",), pg_version=17):
    """An inventory's shape: zones of a number of pgEdge members each, HA where
    there is more than one, replicating db_names."""
    hosts = {f"n{z}-{m}": z for z in range(1, zones + 1)
             for m in range(members)}
    return dict(groups={"pgedge": list(hosts)},
                hostvars={h: {"inventory_hostname": h, "zone": z}
                          for h, z in hosts.items()},
                db_names=list(db_names), pg_version=pg_version,
                is_ha_cluster=members > 1)


# The ultra-ha inventory's shape, which the template is rendered against.
ULTRA_HA = dict(groups={"pgedge": PGEDGE},
                hostvars={h: {"inventory_hostname": h, "zone": ZONE_OF[h]}
                          for h in PGEDGE},
                db_names=["demo"], pg_version=17, is_ha_cluster=True)


def parameters(pg_parameters, backups, zone=1, shape=ULTRA_HA,
               coldfront=False, mesh=False):
    """role_config's parameter layers for an inventory's pg_parameters and the
    shape of its cluster, evaluated as Ansible would. Returns every layer by
    name."""
    role_vars = yaml.safe_load(ROLE_VARS.read_text())
    e = ansible_filters(NativeEnvironment(undefined=StrictUndefined))
    ctx = dict(pg_parameters=pg_parameters, pg_port=5432,
               pg_data="/var/lib/pgsql/17/data", zone=zone,
               spock_exception_behaviour="transdiscard",
               backup_repo_configured=backups, backup_stanza="pgedge-demo-1",
               pg_supports_output_plugin_libraries=True,
               pg_required_preload_libraries=
               role_vars["pg_required_preload_libraries"],
               pg_default_preload_libraries=
               role_vars["pg_default_preload_libraries"],
               coldfront_enabled=coldfront, coldfront_mesh=mesh,
               coldfront_duckdb_role="coldfront_duckdb",
               coldfront_db="coldfront", lakekeeper_host="10.0.0.30",
               lakekeeper_port=8181, lakekeeper_warehouse="wh",
               **shape)
    for name in PARAMETER_LAYERS:
        ctx[name] = e.from_string(role_vars[name]).render(**ctx)
    return ctx


def replica_from_backup(e, requested, backups):
    """role_config's replica_from_backup, evaluated as Ansible would."""
    expr = yaml.safe_load(ROLE_VARS.read_text())["replica_from_backup"]
    return e.from_string(expr).render(patroni_replica_from_backup=requested,
                                      backup_repo_configured=backups)


# role_config's HBA rules for the hosts of other components, in the order each
# reads the one before.
HBA_LAYERS = ("ai_dba_workbench_enabled", "pg_ai_dba_workbench_hba_rules",
              "pg_required_hba_rules")


def hba_rules(groups):
    """role_config's pg_required_hba_rules for an inventory's groups, evaluated
    as Ansible would."""
    role_vars = yaml.safe_load(ROLE_VARS.read_text())
    e = ansible_filters(NativeEnvironment(undefined=StrictUndefined))
    ctx = dict(groups=groups,
               ai_dba_workbench_monitor_user="ai_dba_workbench_monitor")
    for name in HBA_LAYERS:
        ctx[name] = e.from_string(role_vars[name]).render(**ctx)
    return ctx["pg_required_hba_rules"]


def context(e, os_family, backups, replica, hosts_with_facts,
            pg_parameters=None):
    """The template's variables. 'replica' is the inventory's
    patroni_replica_from_backup; what the template sees is derived from it,
    as the Postgres parameters are from 'pg_parameters'."""
    zone = 1
    layers = parameters(pg_parameters or {}, backups, zone)
    in_zone = [h for h in PGEDGE if ZONE_OF[h] == zone]
    groups = {"pgedge": PGEDGE, "haproxy": HAPROXY, "backup": BACKUP}
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
        groups=groups,
        hostvars=hostvars_for(hosts_with_facts),
        nodes_in_zone=in_zone,
        proxies_in_zone=[h for h in HAPROXY if ZONE_OF[h] == zone],
        proxy_node="", custom_hba_rules=[], backup_host="",
        pg_required_hba_rules=hba_rules(groups),
        pgedge_user="pgedge", db_user="admin", replication_user="replicator",
        backup_user="backrest", db_password="p", replication_password="p",
        pg_user_parameters=layers["pg_user_parameters"],
        pg_effective_parameters=layers["pg_effective_parameters"])


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


# What bootstrap.dcs held before its parameters came from pg_parameters, with
# the repository configured. An inventory that sets none must render exactly
# this, give or take spelling: the names are lower case now, and on and off
# are strings. The one value that changed is max_worker_processes, once a fixed
# 12 and now sized from the cluster: 20 for two zones replicating one database.
LEGACY_PARAMETERS = {
    "port": 5432, "ssl": "on",
    "ssl_cert_file": "/var/lib/pgsql/17/data/server.crt",
    "ssl_key_file": "/var/lib/pgsql/17/data/server.key",
    "listen_addresses": "0.0.0.0", "archive_mode": "on",
    "archive_command": "pgbackrest --stanza=pgedge-demo-1 archive-push %p",
    "restore_command": "pgbackrest --stanza=pgedge-demo-1 archive-get %f %p",
    "timezone": "UTC", "wal_level": "logical", "max_worker_processes": 20,
    "max_replication_slots": 16, "max_wal_senders": 16,
    "hot_standby_feedback": "on", "track_commit_timestamp": "on",
    "shared_preload_libraries": "spock, snowflake, pg_stat_statements",
    "output_plugin_libraries": "pgoutput, test_decoding, spock_output",
    "spock.enable_ddl_replication": "on",
    "spock.allow_ddl_from_functions": "on", "spock.include_ddl_repset": "on",
    "spock.exception_behaviour": "transdiscard",
    "spock.conflict_resolution": "last_update_wins",
    "spock.save_resolutions": "on", "spock.conflict_log_level": "DEBUG",
    "snowflake.node": 1,
}

# An inventory exercising each rule of the layering: a name in other case
# overriding a default, a plain addition, a YAML boolean, a null dropping a
# default, libraries merged into the preload list (one of them already there),
# and a parameter Debian's local block would otherwise shadow.
USER_PARAMETERS = {
    "TimeZone": "America/Chicago", "work_mem": "64MB", "jit": False,
    "spock.conflict_log_level": None,
    "shared_preload_libraries": "auto_explain, spock",
    "log_directory": "/var/log/pg",
}


def check_parameters(e, template):
    """The parameters bootstrap.dcs carries, with and without pg_parameters."""
    everyone = set(PGEDGE + HAPROXY + BACKUP)
    failures = []

    def dcs_and_local(os_family, pg_parameters):
        doc = yaml.safe_load(template.render(**context(
            e, os_family, True, False, everyone, pg_parameters)))
        return (doc["bootstrap"]["dcs"]["postgresql"]["parameters"],
                doc["postgresql"].get("parameters") or {})

    for os_family in ("RedHat", "Debian"):
        dcs, _ = dcs_and_local(os_family, None)
        label = f"{os_family} parameters without pg_parameters"
        if dcs != LEGACY_PARAMETERS:
            diff = sorted(set(dcs.items()) ^ set(LEGACY_PARAMETERS.items()))
            failures.append(f"{label}: differs from the legacy set: {diff}")
            print(f"FAIL     {label}")
        else:
            print(f"ok       {label}")

        dcs, local = dcs_and_local(os_family, USER_PARAMETERS)
        checks = {
            "case-folded override": dcs.get("timezone") == "America/Chicago"
                and "TimeZone" not in dcs,
            "added parameter": dcs.get("work_mem") == "64MB",
            "boolean spelled off": dcs.get("jit") == "off",
            "null drops a default": "spock.conflict_log_level" not in dcs,
            "preload libraries merged": dcs.get("shared_preload_libraries")
                == "spock, snowflake, pg_stat_statements, auto_explain",
            "required parameters kept": all(
                dcs.get(k) == LEGACY_PARAMETERS[k]
                for k in ("wal_level", "port", "archive_command",
                          "snowflake.node")),
            # Patroni's local parameters beat the store's, so a Debian default
            # the inventory overrides has to leave the local block.
            "local block yields to pg_parameters": "log_directory" not in local
                and (os_family != "Debian"
                     or local.get("logging_collector") == "on"),
        }
        bad = [name for name, ok in checks.items() if not ok]
        label = f"{os_family} parameters with pg_parameters"
        if bad:
            failures.append(f"{label}: {', '.join(bad)}")
            print(f"FAIL     {label}: {', '.join(bad)}")
        else:
            print(f"ok       {label}")

    # With no repository the archive command is the placeholder, and there is
    # no restore command to give.
    dcs = parameters({}, False)["pg_effective_parameters"]
    label = "parameters without a repository"
    if dcs.get("archive_command") != "/bin/true" or "restore_command" in dcs:
        failures.append(f"{label}: archive_command {dcs.get('archive_command')}"
                        f", restore_command {dcs.get('restore_command')}")
        print(f"FAIL     {label}")
    else:
        print(f"ok       {label}")

    # Setting shared_preload_libraries to null drops the default library but
    # never the ones Spock and snowflake need.
    preload = parameters({"shared_preload_libraries": None}, True)[
        "pg_effective_parameters"]["shared_preload_libraries"]
    label = "null shared_preload_libraries"
    if preload != "spock, snowflake":
        failures.append(f"{label}: got '{preload}'")
        print(f"FAIL     {label}")
    else:
        print(f"ok       {label}")

    # With ColdFront enabled, its libraries load after pg_stat_statements and
    # before the inventory's own, and its settings are required parameters,
    # which init_server refuses from pg_parameters. Without coldfront_mesh
    # there is no DSN for coordinating commits between nodes.
    layers = parameters({"shared_preload_libraries": "auto_explain"}, True,
                        coldfront=True)
    dcs = layers["pg_effective_parameters"]
    checks = {
        "libraries in order": dcs["shared_preload_libraries"]
            == "spock, snowflake, pg_stat_statements, pg_duckdb, coldfront, "
               "auto_explain",
        "autoinstall off": dcs.get("duckdb.autoinstall_known_extensions")
            == "off",
        "settings required": all(
            name in layers["pg_required_parameters"]
            for name in ("duckdb.postgres_role", "coldfront.local_pg_dsn",
                         "coldfront.lakekeeper_endpoint")),
        "no mesh DSN": "coldfront.dblink_self" not in dcs,
    }
    bad = [name for name, ok in checks.items() if not ok]
    label = "ColdFront parameters"
    if bad:
        failures.append(f"{label}: {', '.join(bad)}")
        print(f"FAIL     {label}: {', '.join(bad)}")
    else:
        print(f"ok       {label}")

    # coldfront_mesh adds the DSN that arms the bakery, and the settings that
    # keep an idle peer from looking dead to it, which are defaults an
    # inventory may tune. Its database is then one of db_names, so the sizing
    # counts its Spock manager and subscriptions.
    meshed = dict(ULTRA_HA, db_names=["demo", "coldfront"])
    layers = parameters({}, True, shape=meshed, coldfront=True, mesh=True)
    dcs = layers["pg_effective_parameters"]
    plain = parameters({}, True, coldfront=True)
    checks = {
        "mesh DSN": "application_name=coldfront_dblink"
            in dcs.get("coldfront.dblink_self", ""),
        "status interval": dcs.get("wal_receiver_status_interval") == "1s",
        "peer window": str(dcs.get("coldfront.peer_alive_window_ms"))
            == "5000",
        "tunables not required": not any(
            name in layers["pg_required_parameters"]
            for name in ("wal_receiver_status_interval",
                         "coldfront.peer_alive_window_ms",
                         "coldfront.iceberg_async_parquet")),
        "database counted": int(layers["pg_connectable_dbs"])
            == int(plain["pg_connectable_dbs"]) + 1,
        "subscriptions counted": int(layers["pg_spock_subscriptions"])
            == 2 * int(plain["pg_spock_subscriptions"]),
    }
    bad = [name for name, ok in checks.items() if not ok]
    label = "ColdFront mesh parameters"
    if bad:
        failures.append(f"{label}: {', '.join(bad)}")
        print(f"FAIL     {label}: {', '.join(bad)}")
    else:
        print(f"ok       {label}")

    return failures


# (what it is, cluster shape, pg_parameters, the sized parameters expected)
# The first two are the worked examples in Spock's sizing guide; the next five
# its table of recommended minimums, for one database and no standbys.
SIZING = [
    ("3-node mesh, one database, one standby",
     cluster(3, members=2), {},
     {"max_worker_processes": 20, "max_replication_slots": 16,
      "max_wal_senders": 16}),
    ("5-node mesh, two databases, two standbys",
     cluster(5, members=3, db_names=("app", "ledger")), {},
     {"max_worker_processes": 32, "max_replication_slots": 20,
      "max_wal_senders": 20}),
    *[(f"{n}-node mesh", cluster(n), {},
       {"max_worker_processes": workers, "max_replication_slots": 16,
        "max_wal_senders": 16})
      for n, workers in ((2, 20), (3, 20), (4, 24), (5, 24), (8, 32))],
    ("a single node never falls below the old slot count",
     cluster(1), {},
     {"max_worker_processes": 16, "max_replication_slots": 16,
      "max_wal_senders": 16}),
    ("3-node mesh replicating ten databases",
     cluster(3, db_names=[f"db{i}" for i in range(10)]), {},
     {"max_worker_processes": 64, "max_replication_slots": 42,
      "max_wal_senders": 42}),
    # Counted twice, postgres would round the workers up to 32.
    ("postgres in db_names is one manager, not two",
     cluster(3, db_names=("app", "ledger", "postgres")), {},
     {"max_worker_processes": 28, "max_replication_slots": 16,
      "max_wal_senders": 16}),
    ("more parallel workers grow the worker pool",
     cluster(3), {"Max_Parallel_Workers": 16},
     {"max_worker_processes": 28, "max_replication_slots": 16,
      "max_wal_senders": 16}),
    ("Postgres 18 sizes its origins with the slots",
     cluster(5, members=3, db_names=("app", "ledger"), pg_version=18), {},
     {"max_worker_processes": 32, "max_replication_slots": 20,
      "max_wal_senders": 20, "max_active_replication_origins": 20}),
    ("pg_parameters still wins over the calculation",
     cluster(3), {"max_worker_processes": 40, "max_wal_senders": None},
     {"max_worker_processes": 40, "max_replication_slots": 16}),
]

SIZED = ("max_worker_processes", "max_replication_slots", "max_wal_senders",
         "max_active_replication_origins")


def check_sizing():
    """The worker and slot defaults, sized from clusters of several shapes."""
    failures = []
    for label, shape, pg_parameters, want in SIZING:
        effective = parameters(pg_parameters, True, shape=shape)[
            "pg_effective_parameters"]
        got = {k: effective[k] for k in SIZED if k in effective}
        if got != want:
            failures.append(f"sizing '{label}': expected {want}, got {got}")
            print(f"FAIL     sizing: {label}")
        else:
            print(f"ok       sizing: {label}")
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


def check_ai_dba_workbench(e, template):
    """An AI DBA Workbench host is admitted to every database as the monitoring
    role, and to nothing else, and an inventory without one renders no such
    rule. role_config's pg_required_hba_rules carries the rule, and on an HA
    cluster Patroni's configuration writes it, from which Patroni writes
    pg_hba.conf, so this is the only place it can be checked without a running
    cluster.
    """
    failures = []
    for hosts in ([], AI_DBA_WORKBENCH):
        ctx = context(e, "RedHat", True, False,
                      set(PGEDGE + HAPROXY + BACKUP))
        ctx["groups"] = {**ctx["groups"], "ai_dba_workbench": hosts}
        ctx["hostvars"] = {**ctx["hostvars"],
                           **{h: {"inventory_hostname": h,
                                  "ansible_default_ipv4": {"address": h}}
                              for h in hosts}}
        ctx["pg_required_hba_rules"] = hba_rules(ctx["groups"])
        doc = yaml.safe_load(template.render(**ctx))
        rules = [line for line in doc["postgresql"]["pg_hba"]
                 if "ai_dba_workbench_monitor" in line]
        want = [f"host all ai_dba_workbench_monitor {h}/32 scram-sha-256"
                for h in hosts]
        label = ("an AI DBA Workbench host is admitted as the monitoring role"
                 if hosts else "no AI DBA Workbench host, no monitoring rule")
        if rules == want:
            print(f"ok       {label}")
        else:
            print(f"FAIL     {label}")
            failures.append(f"{label}: expected {want}, rendered {rules}")
    return failures


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
    failures += check_parameters(e, template)
    print()
    failures += check_sizing()
    print()
    failures += check_missing_facts(e, template)
    failures += check_ai_dba_workbench(e, template)
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
