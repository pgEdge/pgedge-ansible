#!/usr/bin/env python3
"""Render setup_ai_dba_workbench's templates and derived settings offline.

Each of the AI DBA Workbench's three services reads a YAML configuration that
setup_ai_dba_workbench writes from the inventory, and nginx reads a site.
Which keys appear depends on the language and embedding models the inventory
names, and a key file named for a provider that is not set stops the Workbench
server from starting at all. The datastore's Postgres instance runs from a unit
the role writes as well, which orders it before all three services. A live run
exercises one combination, with no model, since the test network reaches no
provider, so every combination is rendered here instead: through Ansible
itself, from the role's own defaults, variables and templates, with the output
read back and checked.

The records setup_ai_dba_workbench registers the nodes with are derived from
each node's hostvars, falling back to the Workbench host's own settings, and
are rendered too, for a cluster whose nodes set ports and databases of their
own.

On the nodes, setup_ai_dba_workbench_monitor creates its extensions and grants
in every database the collector reads, so that list is rendered for a node
with and without ColdFront's database, and each playbook that deploys the
Workbench is checked to run the role after every role that creates one. The
rule that admits the Workbench host is role_config's, which setup_postgres
and Patroni's configuration write, so it is rendered for an inventory with
and without a Workbench host.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROLE = REPO / "roles" / "setup_ai_dba_workbench"

TEMPLATES = ("ai-dba-server.yaml", "ai-dba-collector.yaml",
             "ai-dba-alerter.yaml", "pgedge-ai-dba-client.nginx",
             "ai-dba-workbench-postgres.service")

# The role is imported and none of its tasks run: importing is what makes its
# defaults and variables, and role_config's, part of the play, ranked as
# Ansible ranks them in a real run. Each case's settings are then the
# Workbench host's inventory variables, and the nodes' their own, as an
# inventory would set them.
PLAYBOOK = """\
- hosts: ai_dba_workbench
  gather_facts: true
  gather_subset: [min, network]
  tasks:
  - import_role:
      name: setup_ai_dba_workbench
    when: false

  - name: Render the role's templates
    template:
      src: "@ROLE@/templates/{{ item }}.j2"
      dest: "{{ out }}/{{ item }}"
    loop: @TEMPLATES@

  - name: Write out the settings derived from the inventory
    copy:
      content: "{{ derived | to_nice_json }}"
      dest: "{{ out }}/derived.json"
    vars:
      derived:
        connections: "{{ ai_dba_workbench_connections }}"
        passwords: "{{ ai_dba_workbench_connection_passwords }}"
        key_files: "{{ ai_dba_workbench_key_files }}"
        tls_names: "{{ ai_dba_workbench_tls_names }}"
        updates: "{{ ai_dba_workbench_updates }}"
        address: "{{ ansible_default_ipv4.address }}"
        hostname: "{{ ansible_hostname }}"
""".replace("@ROLE@", str(ROLE)).replace(
    "@TEMPLATES@", json.dumps(list(TEMPLATES)))

NODES = {"n1": {"zone": 1, "ansible_default_ipv4": {"address": "10.0.0.10"}},
         "n2": {"zone": 2, "ansible_default_ipv4": {"address": "10.0.0.11"}},
         "n3": {"zone": 3, "ansible_default_ipv4": {"address": "10.0.0.12"}}}
NODE_IPS = ["10.0.0.10", "10.0.0.11", "10.0.0.12"]

LLM_KEY = "/etc/pgedge/ai-dba-llm.key"
EMBEDDING_KEY = "/etc/pgedge/ai-dba-embedding.key"


def no_models(r):
    server, alerter = r["ai-dba-server.yaml"], r["ai-dba-alerter.yaml"]
    return {
        "no llm section": "llm" not in server,
        "no embedding section": "embedding" not in server,
        "tier 2 off": alerter["anomaly"]["tier2"]["enabled"] is False,
        "tier 3 off": alerter["anomaly"]["tier3"]["enabled"] is False,
        "no embedding provider": alerter["llm"]["embedding_provider"]
        == "none",
        "no reasoning provider": alerter["llm"]["reasoning_provider"]
        == "none",
        "no provider sections": set(alerter["llm"])
        == {"embedding_provider", "reasoning_provider"},
        "no key files": r["derived"]["key_files"] == [],
    }


def common(r):
    """What every case renders the same way."""
    server = r["ai-dba-server.yaml"]
    collector = r["ai-dba-collector.yaml"]
    alerter = r["ai-dba-alerter.yaml"]
    nginx = r["pgedge-ai-dba-client.nginx"]
    datastore = {"host": "127.0.0.1", "port": 5432,
                 "database": "ai_workbench", "username": "ai_workbench",
                 "password_file": "/etc/pgedge/ai-dba-db.password"}
    return {
        "server on loopback": server["http"]["address"] == "127.0.0.1:8443",
        "server trusts nginx": server["http"]["trusted_proxies"]
        == ["127.0.0.1/32"],
        "server datastore": server["database"]
        == {**{k: v for k, v in datastore.items() if k != "username"},
            "user": "ai_workbench"},
        "server secret": server["secret_file"] == "/etc/pgedge/ai-dba.secret",
        "private networks closed": server["connection_security"][
            "allow_internal_networks"] is False,
        "collector datastore": collector["datastore"] == datastore,
        "collector secret": collector["secret_file"]
        == "/etc/pgedge/ai-dba.secret",
        "alerter datastore": alerter["datastore"] == datastore,
        "alerter secret": alerter["notifications"]
        == {"enabled": True, "secret_file": "/etc/pgedge/ai-dba.secret"},
        "nginx on its port": "listen 8444 ssl;" in nginx,
        "nginx proxies both locations": nginx.count(
            "proxy_pass http://127.0.0.1:8443;") == 2,
    }


def generated_certificate(r):
    derived = r["derived"]
    return {
        "no HSTS with a self-signed certificate":
            "Strict-Transport-Security" not in r["pgedge-ai-dba-client.nginx"],
        # The inventory name here is not an address, so it is a DNS name.
        "certificate names the host": {
            "DNS:" + derived["hostname"], "IP:" + derived["address"],
            "DNS:w1"} <= set(derived["tls_names"]),
    }


def datastore_unit(r):
    unit = r["ai-dba-workbench-postgres.service"].splitlines()
    exec_start = next(line for line in unit if line.startswith("ExecStart="))
    return {
        "datastore on loopback": "-p 5432 -c listen_addresses=127.0.0.1"
        in exec_start,
        "datastore in its own directory": exec_start.split(" -D ")[1]
        .split()[0].endswith("/ai-dba-workbench"),
        "datastore before every service": {
            line for line in unit if line.startswith("Before=")} == {
            "Before=pgedge-ai-dba-collector.service",
            "Before=pgedge-ai-dba-server.service",
            "Before=pgedge-ai-dba-alerter.service"},
    }


def default_nodes(r):
    connections = r["derived"]["connections"]
    return {
        "every node registered": [c["name"] for c in connections]
        == ["n1", "n2", "n3"],
        "registered by address": [c["host"] for c in connections]
        == NODE_IPS,
        "first database": {c["database_name"] for c in connections}
        == {"demo"},
        "monitoring role": {c["username"] for c in connections}
        == {"ai_dba_workbench_monitor"},
        "encrypted": {c["ssl_mode"] for c in connections} == {"require"},
        "monitored and shared": all(c["is_monitored"] and c["is_shared"]
                                    for c in connections),
        "zone in description": connections[1]["description"]
        == "pgEdge Distributed Postgres node in zone 2 of cluster demo",
        "nodes allowed": r["ai-dba-server.yaml"]["connection_security"][
            "allowed_hosts"] == NODE_IPS,
    }


def anthropic_and_openai(r):
    server, alerter = r["ai-dba-server.yaml"], r["ai-dba-alerter.yaml"]
    return {
        "chat model": server["llm"] == {
            "provider": "anthropic", "model": "claude-sonnet-4-5",
            "anthropic_api_key_file": LLM_KEY},
        "embedding model": server["embedding"] == {
            "enabled": True, "provider": "openai",
            "model": "text-embedding-3-small",
            "openai_api_key_file": EMBEDDING_KEY},
        "both tiers on": alerter["anomaly"]["tier2"]["enabled"] is True
        and alerter["anomaly"]["tier3"]["enabled"] is True,
        "alerter providers": alerter["llm"] == {
            "embedding_provider": "openai", "reasoning_provider": "anthropic",
            "anthropic": {"reasoning_model": "claude-sonnet-4-5",
                          "api_key_file": LLM_KEY},
            "openai": {"embedding_model": "text-embedding-3-small",
                       "api_key_file": EMBEDDING_KEY}},
        "both key files": r["derived"]["key_files"] == [LLM_KEY,
                                                         EMBEDDING_KEY],
    }


def ollama_for_both(r):
    server, alerter = r["ai-dba-server.yaml"], r["ai-dba-alerter.yaml"]
    url = "http://10.0.0.50:11434"
    return {
        "chat through ollama": server["llm"] == {
            "provider": "ollama", "model": "qwen2.5:7b-instruct",
            "ollama_url": url},
        "embeddings share its address": server["embedding"] == {
            "enabled": True, "provider": "ollama",
            "model": "nomic-embed-text", "ollama_url": url},
        "one shared alerter section": alerter["llm"]["ollama"] == {
            "base_url": url, "reasoning_model": "qwen2.5:7b-instruct",
            "embedding_model": "nomic-embed-text"},
        "no key files": r["derived"]["key_files"] == [],
    }


def openai_for_both(r):
    server, alerter = r["ai-dba-server.yaml"], r["ai-dba-alerter.yaml"]
    return {
        "chat key": server["llm"].get("openai_api_key_file") == LLM_KEY,
        "embedding key": server["embedding"].get("openai_api_key_file")
        == EMBEDDING_KEY,
        "alternative endpoint for both":
            server["llm"].get("openai_base_url") == "https://llm.example.com"
            and server["embedding"].get("openai_base_url")
            == "https://llm.example.com",
        "one shared alerter section": set(alerter["llm"]["openai"])
        == {"reasoning_model", "embedding_model", "api_key_file",
            "base_url"},
        "both key files": r["derived"]["key_files"] == [LLM_KEY,
                                                         EMBEDDING_KEY],
    }


def voyage_embeddings_only(r):
    server, alerter = r["ai-dba-server.yaml"], r["ai-dba-alerter.yaml"]
    return {
        "no llm section": "llm" not in server,
        "voyage embeddings": server["embedding"].get("voyage_api_key_file")
        == EMBEDDING_KEY,
        "tier 2 alone": alerter["anomaly"]["tier2"]["enabled"] is True
        and alerter["anomaly"]["tier3"]["enabled"] is False,
        "no reasoning provider": alerter["llm"]["reasoning_provider"]
        == "none",
        "embedding key alone": r["derived"]["key_files"] == [EMBEDDING_KEY],
    }


def supplied_certificate(r):
    return {"HSTS with the inventory's certificate":
            'Strict-Transport-Security "max-age=31536000"'
            in r["pgedge-ai-dba-client.nginx"]}


def nodes_of_their_own(r):
    connections = {c["name"]: c for c in r["derived"]["connections"]}
    return {
        "node's own port": connections["n2"]["port"] == 5433,
        "node's own first database": connections["n2"]["database_name"]
        == "app",
        "others keep the defaults": connections["n1"]["port"] == 5432
        and connections["n1"]["database_name"] == "demo",
        "node's own password": r["derived"]["passwords"]
        == {"n1": "MonitorPass1", "n2": "OtherPass2", "n3": "MonitorPass1"},
        "extra hosts allowed": r["ai-dba-server.yaml"]["connection_security"][
            "allowed_hosts"] == NODE_IPS + ["10.9.9.0/24"],
    }


def registered(name, **drift):
    """A node's record as the Workbench returns it, with any drift laid over
    what the inventory describes. The API adds fields of its own, which are
    not compared."""
    number = int(name[1:])
    record = {"id": number, "name": name, "owner_username": "admin",
              "membership_source": "auto",
              "description": "pgEdge Distributed Postgres node in zone "
                             f"{number} of cluster demo",
              "host": f"10.0.0.{9 + number}", "port": 5432,
              "database_name": "demo", "username": "ai_dba_workbench_monitor",
              "ssl_mode": "require", "is_monitored": True, "is_shared": True}
    record.update(drift)
    return {"json": {k: v for k, v in record.items() if v is not None}}


# The record of the passwords the Workbench was last given, as slurp returns
# it, holding what the inventory's passwords now digest to. Left to Ansible to
# evaluate, so the digest is the role's own.
RECORD_MATCHES = {
    "content": "{{ ai_dba_workbench_passwords_digest | b64encode }}"}


def drifted_node(r):
    return {"only the drifted fields": r["derived"]["updates"] == [
        {"id": 2, "name": "n2",
         "changes": {"port": 5432, "ssl_mode": "require"}}]}


def passwords_changed(r):
    return {"every registered node given its password":
            r["derived"]["updates"] == [
                {"id": 1, "name": "n1",
                 "changes": {"password": "MonitorPass1"}},
                {"id": 3, "name": "n3",
                 "changes": {"password": "MonitorPass1"}}]}


def nothing_to_update(r):
    return {"no update": r["derived"]["updates"] == []}


def monitoring_database(r):
    return {"database named for every node":
            {c["database_name"] for c in r["derived"]["connections"]}
            == {"postgres"}}


# name, node overrides, Workbench host settings, checks
CASES = [
    ("no language or embedding model", {}, {},
     [common, no_models, generated_certificate, default_nodes,
      datastore_unit]),
    ("Anthropic chat and OpenAI embeddings", {},
     {"ai_dba_workbench_llm_provider": "anthropic",
      "ai_dba_workbench_llm_model": "claude-sonnet-4-5",
      "ai_dba_workbench_llm_api_key": "llm-key",
      "ai_dba_workbench_embedding_provider": "openai",
      "ai_dba_workbench_embedding_model": "text-embedding-3-small",
      "ai_dba_workbench_embedding_api_key": "embedding-key"},
     [common, anthropic_and_openai]),
    ("Ollama for both models", {},
     {"ai_dba_workbench_llm_provider": "ollama",
      "ai_dba_workbench_llm_model": "qwen2.5:7b-instruct",
      "ai_dba_workbench_llm_base_url": "http://10.0.0.50:11434",
      "ai_dba_workbench_embedding_provider": "ollama",
      "ai_dba_workbench_embedding_model": "nomic-embed-text"},
     [common, ollama_for_both]),
    ("OpenAI for both models, through another endpoint", {},
     {"ai_dba_workbench_llm_provider": "openai",
      "ai_dba_workbench_llm_model": "gpt-4o-mini",
      "ai_dba_workbench_llm_api_key": "llm-key",
      "ai_dba_workbench_llm_base_url": "https://llm.example.com",
      "ai_dba_workbench_embedding_provider": "openai",
      "ai_dba_workbench_embedding_model": "text-embedding-3-small"},
     [common, openai_for_both]),
    ("Voyage embeddings without a language model", {},
     {"ai_dba_workbench_embedding_provider": "voyage",
      "ai_dba_workbench_embedding_model": "voyage-3",
      "ai_dba_workbench_embedding_api_key": "embedding-key"},
     [common, voyage_embeddings_only]),
    ("a certificate from the inventory", {},
     {"ai_dba_workbench_tls_cert_source": "/srv/tls/workbench.crt",
      "ai_dba_workbench_tls_key_source": "/srv/tls/workbench.key"},
     [common, supplied_certificate]),
    ("nodes with ports, databases and passwords of their own",
     {"n2": {"pg_port": 5433, "db_names": ["app", "other"],
             "ai_dba_workbench_monitor_password": "OtherPass2"}},
     {"ai_dba_workbench_monitor_password": "MonitorPass1",
      "ai_dba_workbench_allowed_hosts": ["10.9.9.0/24"]},
     [common, nodes_of_their_own]),
    ("a monitoring database named", {},
     {"ai_dba_workbench_monitor_db": "postgres"},
     [common, monitoring_database]),
    ("registered nodes as the inventory describes them", {},
     {"ai_dba_workbench_registered": {"results": [registered("n1"),
                                        registered("n2")]},
      "ai_dba_workbench_passwords_slurp": RECORD_MATCHES},
     [nothing_to_update]),
    ("a registered node that has drifted", {},
     {"ai_dba_workbench_registered": {"results": [
         registered("n1"), registered("n2", port=6432, ssl_mode=None)]},
      "ai_dba_workbench_passwords_slurp": RECORD_MATCHES},
     [drifted_node]),
    ("monitoring passwords changed since the record", {},
     {"ai_dba_workbench_monitor_password": "MonitorPass1",
      "ai_dba_workbench_registered": {"results": [registered("n1"),
                                        registered("n3")]},
      "ai_dba_workbench_passwords_slurp": {"content": "c3RhbGU="}},
     [passwords_changed]),
    ("a new secret beside an unchanged record", {},
     {"ai_dba_workbench_monitor_password": "MonitorPass1",
      "ai_dba_workbench_secret_generated": {"changed": True},
      "ai_dba_workbench_registered": {"results": [registered("n1"),
                                        registered("n3")]},
      "ai_dba_workbench_passwords_slurp": RECORD_MATCHES},
     [passwords_changed]),
    ("no record of the monitoring passwords", {},
     {"ai_dba_workbench_monitor_password": "MonitorPass1",
      "ai_dba_workbench_registered": {"results": [registered("n1"),
                                        registered("n3")]},
      "ai_dba_workbench_passwords_slurp": {"skipped": True}},
     [passwords_changed]),
]


# setup_ai_dba_workbench_monitor imported the same way, on a node, to write out
# the databases it makes its extensions and grants in, and the rules
# role_config gives setup_postgres and Patroni's configuration.
MONITOR_PLAYBOOK = """\
- hosts: pgedge
  gather_facts: false
  tasks:
  - import_role:
      name: setup_ai_dba_workbench_monitor
    when: false

  - name: Write out the databases the collector reads
    copy:
      content: "{{ ai_dba_workbench_monitored_dbs | to_json }}"
      dest: "{{ out }}/monitored_dbs.json"

  - name: Write out the rules for the hosts of other components
    copy:
      content: "{{ pg_required_hba_rules | to_json }}"
      dest: "{{ out }}/hba_rules.json"
"""

MONITOR_CASES = [
    ("the databases a node without ColdFront monitors", {},
     ["demo", "postgres"]),
    ("ColdFront's database apart from db_names", {"coldfront_enabled": True},
     ["demo", "postgres", "coldfront"]),
    ("ColdFront's database in db_names, in mesh mode",
     {"coldfront_enabled": True, "coldfront_mesh": True,
      "db_names": ["demo", "coldfront"]},
     ["demo", "coldfront", "postgres"]),
]

# The rules for the hosts of other components, for an inventory with and
# without a Workbench host. Each names its hosts, which setup_postgres and
# Patroni's configuration resolve to their addresses.
HBA_CASES = [
    ("no Workbench host, no rule beyond the cluster's own", {}, []),
    ("the Workbench host, as the monitoring role, to every database",
     {"ai_dba_workbench": {"hosts": {"w1": {}}}},
     [{"hosts": ["w1"], "users": "ai_dba_workbench_monitor",
       "databases": "all"}]),
    ("the monitoring role the inventory names",
     {"ai_dba_workbench": {"hosts": {"w1": {}}},
      "all": {"vars": {"ai_dba_workbench_monitor_user": "watcher"}}},
     [{"hosts": ["w1"], "users": "watcher", "databases": "all"}]),
]

# The playbooks that deploy the Workbench. Each has to run
# setup_ai_dba_workbench_monitor after the roles that start Postgres on the
# nodes, create the databases the collector reads, setup_coldfront_db's among
# them, and put those databases into Spock, and before setup_ai_dba_workbench
# registers the nodes. A database created after it would hold none of the
# extensions.
PLAYBOOKS = ("sample-playbooks/simple-cluster-ai-dba-workbench/playbook.yaml",
             "sample-playbooks/ultra-ha-ai-dba-workbench/playbook.yaml",
             "tests/playbooks/simple-cluster.yml",
             "tests/playbooks/ultra-ha.yml")
EARLIER_ROLES = ("setup_postgres", "setup_patroni", "setup_coldfront_db",
                 "setup_pgedge")


def roles_in_order(playbook):
    order = []
    for play in yaml.safe_load((REPO / playbook).read_text()):
        for entry in play.get("roles", []):
            order.append(entry if isinstance(entry, str) else entry["role"])
        for task in play.get("tasks", []):
            if "include_role" in task:
                order.append(task["include_role"]["name"])
    return order


def monitor_role_placed(order):
    if "setup_ai_dba_workbench_monitor" not in order:
        return {"runs setup_ai_dba_workbench_monitor": False}
    at = order.index("setup_ai_dba_workbench_monitor")
    return {
        "after the roles that build the nodes' databases": all(
            i < at for i, role in enumerate(order) if role in EARLIER_ROLES),
        "before setup_ai_dba_workbench":
            at < order.index("setup_ai_dba_workbench"),
    }


def ansible(playbook, inventory, workdir, out):
    (workdir / "inventory.json").write_text(json.dumps(inventory))
    env = dict(os.environ,
               ANSIBLE_CONFIG=str(workdir / "ansible.cfg"),
               ANSIBLE_ROLES_PATH=str(REPO / "roles"),
               ANSIBLE_NOCOLOR="1",
               ANSIBLE_LOCALHOST_WARNING="0",
               ANSIBLE_INVENTORY_UNPARSED_WARNING="0")
    return subprocess.run(
        ["ansible-playbook", "-i", str(workdir / "inventory.json"),
         "-e", "out=" + str(out),
         str(workdir / playbook)],
        env=env, capture_output=True, text=True)


def render_monitored_dbs(settings, workdir):
    out = workdir / "out"
    out.mkdir(exist_ok=True)
    for f in out.iterdir():
        f.unlink()
    inventory = {"pgedge": {"hosts": {"n1": {
        "ansible_connection": "local",
        "ansible_python_interpreter": sys.executable,
        **settings}}}}
    result = ansible("monitor.yml", inventory, workdir, out)
    if result.returncode != 0:
        return None, result.stdout + result.stderr
    return json.loads((out / "monitored_dbs.json").read_text()), ""


def render_hba_rules(groups, workdir):
    out = workdir / "out"
    out.mkdir(exist_ok=True)
    for f in out.iterdir():
        f.unlink()
    inventory = {"pgedge": {"hosts": {"n1": {
        "ansible_connection": "local",
        "ansible_python_interpreter": sys.executable}}},
        **groups}
    result = ansible("monitor.yml", inventory, workdir, out)
    if result.returncode != 0:
        return None, result.stdout + result.stderr
    return json.loads((out / "hba_rules.json").read_text()), ""


def render(node_overrides, settings, workdir):
    out = workdir / "out"
    out.mkdir(exist_ok=True)
    for f in out.iterdir():
        f.unlink()
    inventory = {
        "pgedge": {"hosts": {h: {**v, **node_overrides.get(h, {})}
                             for h, v in NODES.items()}},
        "ai_dba_workbench": {"hosts": {"w1": {
            "ansible_connection": "local",
            "ansible_python_interpreter": sys.executable,
            # What the role registers before it reads these, where a case
            # gives none: a secret that was already there, no registered
            # nodes, and no record read.
            "ai_dba_workbench_secret_generated": {"changed": False,
                                                  "skipped": True},
            "ai_dba_workbench_registered": {"results": []},
            "ai_dba_workbench_passwords_slurp": {"skipped": True},
            **settings}}},
    }
    result = ansible("play.yml", inventory, workdir, out)
    if result.returncode != 0:
        return None, result.stdout + result.stderr
    rendered = {}
    for name in TEMPLATES:
        text = (out / name).read_text()
        rendered[name] = text if name.endswith((".nginx", ".service")) \
            else yaml.safe_load(text)
    rendered["derived"] = json.loads((out / "derived.json").read_text())
    return rendered, ""


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp)
        (workdir / "play.yml").write_text(PLAYBOOK)
        # Not the suite's own ansible.cfg, which is for reaching containers.
        (workdir / "ansible.cfg").write_text("[defaults]\n")
        for name, node_overrides, settings, checks in CASES:
            rendered, output = render(node_overrides, settings, workdir)
            if rendered is None:
                failures += 1
                print(f"FAIL     {name}: the render failed")
                print(output)
                continue
            failed = [check for checker in checks
                      for check, ok in checker(rendered).items() if not ok]
            if failed:
                failures += 1
                print(f"FAIL     {name}: {', '.join(failed)}")
                for template in TEMPLATES[:3]:
                    print(f"--- {template}")
                    print(yaml.safe_dump(rendered[template]))
                print(json.dumps(rendered["derived"], indent=2))
            else:
                print(f"ok       {name}")
        (workdir / "monitor.yml").write_text(MONITOR_PLAYBOOK)
        for name, settings, expected in MONITOR_CASES:
            monitored, output = render_monitored_dbs(settings, workdir)
            if monitored is None:
                failures += 1
                print(f"FAIL     {name}: the render failed")
                print(output)
            elif monitored != expected:
                failures += 1
                print(f"FAIL     {name}: {monitored}, not {expected}")
            else:
                print(f"ok       {name}")
        for name, groups, expected in HBA_CASES:
            rules, output = render_hba_rules(groups, workdir)
            if rules is None:
                failures += 1
                print(f"FAIL     {name}: the render failed")
                print(output)
            elif rules != expected:
                failures += 1
                print(f"FAIL     {name}: {rules}, not {expected}")
            else:
                print(f"ok       {name}")
    for playbook in PLAYBOOKS:
        failed = [check for check, ok
                  in monitor_role_placed(roles_in_order(playbook)).items()
                  if not ok]
        if failed:
            failures += 1
            print(f"FAIL     {playbook}: {', '.join(failed)}")
        else:
            print(f"ok       {playbook}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
