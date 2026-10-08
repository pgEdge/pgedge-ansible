#!/usr/bin/env python3
"""Render setup_etcd's template offline and check the types etcd reads.

etcd parses its configuration file into a typed struct and refuses to start on
a mismatch. auto-compaction-retention is a string to etcd even when it is a bare
revision count or a number of hours, and an inventory that writes
'etcd_auto_compaction_retention: 1' hands the template an integer. That
mistake surfaces only when etcd fails to start on every node of a zone, so each
case below renders a retention an inventory might write and checks the YAML
etcd would read.

quota-backend-bytes is rendered bare and left unfiltered: YAML reads a number as
an integer however Ansible passed it, and anything else should stop etcd rather
than be coerced by '| int' into 0, which etcd reads as its default quota.

The renders use Ansible's Jinja settings rather than bare Jinja2's: the template
module turns trim_blocks on, and this template opens with '{%- %}' tags whose
whitespace handling depends on it.
"""

import pathlib
import sys

import yaml
from jinja2 import Environment, StrictUndefined

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEMPLATE = REPO / "roles" / "setup_etcd" / "templates" / "etcd.yaml.j2"
DEFAULTS = REPO / "roles" / "setup_etcd" / "defaults" / "main.yaml"

NODES = ["192.168.6.10", "192.168.6.11", "192.168.6.12"]

# Each case overrides the role defaults the way an inventory would, and names
# the values etcd must then read back.
CASES = {
    "defaults": (
        {},
        {"auto-compaction-mode": "periodic",
         "auto-compaction-retention": "1h",
         "quota-backend-bytes": 2147483648},
    ),
    "retention in bare hours": (
        {"etcd_auto_compaction_retention": 1},
        {"auto-compaction-retention": "1"},
    ),
    "retention in revisions": (
        {"etcd_auto_compaction_mode": "revision",
         "etcd_auto_compaction_retention": 10000},
        {"auto-compaction-mode": "revision",
         "auto-compaction-retention": "10000"},
    ),
    "compaction disabled": (
        {"etcd_auto_compaction_retention": 0},
        {"auto-compaction-retention": "0"},
    ),
}

env = Environment(trim_blocks=True, keep_trailing_newline=True,
                  undefined=StrictUndefined)


def context_for(overrides):
    context = yaml.safe_load(DEFAULTS.read_text())
    context.update(overrides)
    context.update({
        "nodes_in_zone": NODES,
        "hostvars": {node: {"inventory_hostname": node,
                            "ansible_hostname": "node%d" % i}
                     for i, node in enumerate(NODES)},
        "inventory_hostname": NODES[0],
        "ansible_hostname": "node0",
        "ansible_default_ipv4": {"address": NODES[0]},
    })
    return context


def main():
    template = env.from_string(TEMPLATE.read_text())
    failures = 0

    for name, (overrides, expected) in CASES.items():
        parsed = yaml.safe_load(template.render(context_for(overrides)))
        wrong = {key: parsed.get(key) for key, value in expected.items()
                 if parsed.get(key) != value
                 or type(parsed.get(key)) is not type(value)}
        if not wrong:
            print(f"ok       {name}")
            continue

        failures += 1
        print(f"WRONG    {name}")
        for key, value in wrong.items():
            print(f"  {key}: rendered {value!r}, etcd needs {expected[key]!r}")

    if failures:
        print(f"\n{failures} render(s) would hand etcd a value it cannot read.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
