#!/usr/bin/env python3
"""Run init_server's validation against inventories that set pg_parameters.

init_server refuses an inventory whose pg_parameters would be overridden or
would break the cluster, and an HA zone whose nodes disagree on them. It also
refuses ColdFront where its settings could not work: without a catalog or a
complete object store, on a Postgres release it has no packages for, or on an
HA cluster, and a Lakekeeper host with the default catalog password, colliding
ports, or a place in the pgedge group as well. ColdFront's settings are the
collection's own once it is enabled, so pg_parameters may set them only where
it is not. The e2e inventories are ones the validation accepts, so the
refusals are checked here instead, without any containers: the validation
reads only the inventory and the controller's own facts, so each case runs the
real tasks against hosts that are the controller itself.

Each case names the inventory's hosts and whether the run must pass. A host is
in the pgedge group unless its "groups" entry names others. A refusal must
also say why, in words an operator can act on.

An override smaller than the collection's calculated worker and slot pools is
refused too, while one at least as large passes.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

PLAYBOOK = """\
- hosts: all
  gather_facts: true
  gather_subset: [min]
  tasks:
  - include_role:
      name: init_server
      tasks_from: validate.yaml
"""

# Every pgedge host needs real passwords, or validation refuses the defaults
# before it reaches pg_parameters.
BASE = {
    "ansible_connection": "local",
    "ansible_python_interpreter": sys.executable,
    "db_password": "ValidatePass1",
    "pgedge_password": "ValidatePass2",
    "replication_password": "ValidatePass3",
    "backup_password": "ValidatePass4",
}

SIMPLE = {"is_ha_cluster": False}
HA = {"is_ha_cluster": True}

TUNED = {"work_mem": "64MB", "TimeZone": "Etc/UTC", "jit": False,
         "shared_preload_libraries": ["auto_explain"]}

# The object store settings both kinds of host need.
OBJECT_STORE = {"lakekeeper_host": "10.0.0.30",
                "coldfront_s3_access_key": "coldfront",
                "coldfront_s3_secret_key": "ValidateSecret"}

COLDFRONT = {"coldfront_enabled": True, **OBJECT_STORE}

# A pgEdge node beside a Lakekeeper host, since every inventory has some.
NODE = {**SIMPLE, **COLDFRONT, "zone": 1}

LAKEKEEPER = {"groups": ["lakekeeper"], **OBJECT_STORE,
              "lakekeeper_db_password": "ValidatePass5"}

# Three single-node zones replicating one database: 20 workers, 16 slots.
MESH = {f"n{z}": {**SIMPLE, "zone": z} for z in (1, 2, 3)}


def mesh(pg_parameters):
    return {h: {**v, "pg_parameters": pg_parameters} for h, v in MESH.items()}


# (name, {host: vars}, passes, fragments the refusal must contain)
CASES = [
    ("accepted parameters",
     {"n1": {**SIMPLE, "zone": 1, "pg_parameters": TUNED},
      "n2": {**SIMPLE, "zone": 2, "pg_parameters": TUNED}},
     True, []),
    ("protected parameters, in any letter case",
     {"n1": {**SIMPLE, "zone": 1,
             "pg_parameters": {"work_mem": "64MB", "Port": 5433,
                               "wal_level": "replica",
                               "hba_file": "/tmp/hba.conf"}}},
     False, ["hba_file (use custom_hba_rules instead)",
             "port (set pg_port instead)",
             "wal_level ("]),
    ("a parameter Patroni sets",
     {"n1": {**HA, "zone": 1, "pg_parameters": {"hot_standby": False}}},
     False, ["hot_standby (Patroni sets it)"]),
    ("pg_parameters that is not a mapping",
     {"n1": {**SIMPLE, "zone": 1, "pg_parameters": ["work_mem=64MB"]}},
     False, ["pg_parameters must map Postgres parameter names to values"]),
    ("shared_preload_libraries of the wrong shape",
     {"n1": {**SIMPLE, "zone": 1,
             "pg_parameters": {"shared_preload_libraries": 42}}},
     False, ["a list or a comma-separated"]),
    ("shared_preload_libraries given as a mapping",
     {"n1": {**SIMPLE, "zone": 1,
             "pg_parameters": {"shared_preload_libraries":
                               {"auto_explain": True}}}},
     False, ["a list or a comma-separated"]),
    ("a parameter named twice in different letter case",
     {"n1": {**SIMPLE, "zone": 1,
             "pg_parameters": {"TimeZone": "UTC", "timezone": "Etc/UTC"}}},
     False, ["sets timezone more than once"]),
    ("an HA zone whose nodes agree",
     {"n1": {**HA, "zone": 1, "pg_parameters": TUNED},
      "n2": {**HA, "zone": 1, "pg_parameters": TUNED},
      "n3": {**HA, "zone": 2, "pg_parameters": {"work_mem": "8MB"}}},
     True, []),
    ("an HA zone whose nodes agree in different letter case",
     {"n1": {**HA, "zone": 1, "pg_parameters": {"TimeZone": "Etc/UTC"}},
      "n2": {**HA, "zone": 1, "pg_parameters": {"timezone": "Etc/UTC"}}},
     True, []),
    ("an HA zone whose nodes disagree",
     {"n1": {**HA, "zone": 1, "pg_parameters": TUNED},
      "n2": {**HA, "zone": 1, "pg_parameters": {"work_mem": "8MB"}}},
     False, ["pg_parameters must be the same on every node of zone 1"]),
    ("pools left to the collection",
     mesh({"work_mem": "64MB"}), True, []),
    ("pools overridden upward",
     mesh({"max_worker_processes": 32, "max_wal_senders": "20"}),
     True, []),
    ("worker pool overridden below the calculation",
     mesh({"max_worker_processes": 12}),
     False,
     ["max_worker_processes to 12 where the cluster needs at least 20"]),
    ("pools removed in favor of Postgres's defaults",
     mesh({"max_wal_senders": None, "Max_Replication_Slots": 10}),
     False,
     ["max_replication_slots to 10 where the cluster needs at least 16",
      "max_wal_senders to null where the cluster needs at least 16"]),
    ("more parallel workers outgrowing a fixed worker pool",
     mesh({"max_parallel_workers": 16, "max_worker_processes": 24}),
     False,
     ["max_worker_processes to 24 where the cluster needs at least 28"]),
    ("more databases outgrowing the slot pool",
     {h: {**v, "db_names": [f"db{i}" for i in range(5)],
          "pg_parameters": {"max_replication_slots": 16}}
      for h, v in MESH.items()},
     False,
     ["max_replication_slots to 16 where the cluster needs at least 22"]),
    ("ColdFront's own settings",
     {"n1": {**SIMPLE, **COLDFRONT, "zone": 1,
             "pg_parameters": {"duckdb.autoinstall_known_extensions": True}}},
     False, ["duckdb.autoinstall_known_extensions (the collection requires"]),
    ("pg_duckdb's settings without ColdFront",
     {"n1": {**SIMPLE, "zone": 1,
             "pg_parameters": {"duckdb.autoinstall_known_extensions": True}}},
     True, []),
    ("ColdFront without a catalog",
     {"n1": {**SIMPLE, "coldfront_enabled": True, "zone": 1}},
     False, ["needs lakekeeper_host set"]),
    ("ColdFront on an HA cluster without mesh mode",
     {"n1": {**HA, **COLDFRONT, "zone": 1}},
     False, ["on an HA cluster coldfront_mesh set to true"]),
    ("ColdFront on an HA cluster in mesh mode",
     {"n1": {**HA, **COLDFRONT, "zone": 1, "coldfront_mesh": True,
             "db_names": ["demo", "coldfront"]}},
     True, []),
    ("ColdFront's mesh mode without its database in Spock",
     {"n1": {**NODE, "coldfront_mesh": True}},
     False, ["needs coldfront_db (coldfront) listed in db_names"]),
    ("ColdFront's mesh mode with its database in Spock",
     {"n1": {**NODE, "coldfront_mesh": True,
             "db_names": ["demo", "coldfront"]}},
     True, []),
    ("ColdFront's mesh settings",
     {"n1": {**NODE, "coldfront_mesh": True,
             "db_names": ["demo", "coldfront"],
             "pg_parameters": {"wal_receiver_status_interval": "10s"}}},
     False, ["wal_receiver_status_interval (the collection requires"]),
    ("ColdFront and its Lakekeeper host",
     {"n1": NODE, "k1": LAKEKEEPER},
     True, []),
    ("ColdFront on a Postgres release without its packages",
     {"n1": {**SIMPLE, **COLDFRONT, "zone": 1, "pg_version": 15}},
     False, ["pg_version is 15"]),
    ("ColdFront without object store credentials",
     {"n1": {**SIMPLE, "coldfront_enabled": True,
             "lakekeeper_host": "10.0.0.30", "zone": 1}},
     False, ["coldfront_s3_access_key, coldfront_s3_secret_key"]),
    ("an object store endpoint that is not a URL",
     {"n1": {**SIMPLE, **COLDFRONT, "zone": 1,
             "coldfront_s3_endpoint": "s3.example.com"}},
     False, ["invalid on n1: coldfront_s3_endpoint"]),
    ("an object store endpoint with a port",
     {"n1": {**SIMPLE, **COLDFRONT, "zone": 1,
             "coldfront_s3_endpoint": "http://10.0.0.31:8333"}},
     True, []),
    ("a Lakekeeper host with no object store bucket",
     {"n1": NODE, "k1": {**LAKEKEEPER, "coldfront_s3_bucket": ""}},
     False, ["invalid on k1: coldfront_s3_bucket"]),
    ("a Lakekeeper host with the default catalog password",
     {"n1": NODE, "k1": {**LAKEKEEPER, "lakekeeper_db_password": "secret"}},
     False, ["lakekeeper_db_password is still set to the default"]),
    ("a Lakekeeper host serving its catalog on Postgres's port",
     {"n1": NODE, "k1": {**LAKEKEEPER, "lakekeeper_port": 5432}},
     False, ["they are 5432, 5432 and 9000"]),
    ("a Lakekeeper host that is also a pgEdge node",
     {"n1": {**SIMPLE, **COLDFRONT, **LAKEKEEPER, "zone": 1,
             "groups": ["pgedge", "lakekeeper"]}},
     False, ["both the 'pgedge' and 'lakekeeper' groups"]),
]


def run(hosts, workdir):
    groups = {}
    for host, given in hosts.items():
        given = dict(given)
        for group in given.pop("groups", ["pgedge"]):
            groups.setdefault(group, {"hosts": {}})["hosts"][host] = {
                **BASE, **given}
    inventory = workdir / "inventory.json"
    inventory.write_text(json.dumps(groups))
    env = dict(os.environ,
               ANSIBLE_CONFIG=str(workdir / "ansible.cfg"),
               ANSIBLE_ROLES_PATH=str(REPO / "roles"),
               ANSIBLE_NOCOLOR="1",
               ANSIBLE_LOCALHOST_WARNING="0",
               ANSIBLE_INVENTORY_UNPARSED_WARNING="0")
    result = subprocess.run(
        ["ansible-playbook", "-i", str(inventory), str(workdir / "play.yml")],
        env=env, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        (workdir / "play.yml").write_text(PLAYBOOK)
        # Not the suite's own ansible.cfg, which is for reaching containers.
        (workdir / "ansible.cfg").write_text("[defaults]\n")
        for name, hosts, passes, fragments in CASES:
            code, output = run(hosts, workdir)
            problems = []
            if passes and code != 0:
                problems.append("validation refused it")
            if not passes and code == 0:
                problems.append("validation accepted it")
            if not passes and code != 0 and "fatal:" not in output:
                problems.append("the run failed before validation could")
            problems += [f"the refusal does not say {f!r}"
                         for f in fragments if f not in output]
            if problems:
                failures += 1
                print(f"FAIL     {name}: {'; '.join(problems)}")
                print(output)
            else:
                print(f"ok       {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
