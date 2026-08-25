#!/usr/bin/env python3
"""Render setup_haproxy's template offline and compare it against fixtures.

Pooling is additive: a cluster that leaves pgbouncer_enabled unset must get
exactly the haproxy.cfg it got before the pooler existed. The live matrix
cannot observe that -- every cluster in it pools -- so the invariant is checked
here instead, against expected/haproxy-unpooled.cfg, which was captured by
rendering the template as it stood on main before the pooled listener was
added. The pooled fixture beside it is the counterpart: it holds the output a
pooled cluster should get, so a change to that listener has to be looked at
rather than merely deployed.

The pooled set is derived here the way a real run derives it -- from
role_config's own vars, off nothing but pgbouncer_enabled in hostvars -- so
these fixtures also pin the rule that makes pooling cluster-wide: the pooled
listener carries the same servers as the direct one, never a subset.

Usage:
    python3 tests/render/check-haproxy.py            # check, exit 1 on drift
    python3 tests/render/check-haproxy.py --update   # re-baseline the fixtures

--update rewrites the fixtures from the current template. For the pooled
fixture that is routine; for the unpooled one it means accepting that the
no-pooling output has changed, which is the thing this file exists to stop.
Read the diff before running it.

The renders use Ansible's Jinja settings rather than bare Jinja2's: the
template module turns trim_blocks on, so a '{%- if %}' that renders cleanly
under the defaults strips the newline on both sides of the tag on a real run.
That once welded two config lines together and left pgBouncer refusing to
start, so this harness has to match the deployment exactly.
"""

import argparse
import ast
import difflib
import pathlib
import re
import sys

import yaml
from jinja2 import Environment, StrictUndefined

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEMPLATE = REPO / "roles" / "setup_haproxy" / "templates" / "haproxy.cfg.j2"
FIXTURES = HERE / "expected"

# One zone of a cluster. Addresses rather than names, as the test inventories
# use. Every node either pools or none does, so the cases below are a single
# boolean -- the same one an inventory sets on the 'pgedge' group.
NODES = ["192.168.6.10", "192.168.6.11", "192.168.6.12"]

CASES = {
    "haproxy-unpooled.cfg": False,
    "haproxy-pooled.cfg": True,
}

env = Environment(trim_blocks=True, keep_trailing_newline=True,
                  undefined=StrictUndefined)


def ansible_bool(value):
    """Ansible's bool filter, which accepts the strings an inventory may use."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "on", "1", "y", "t")
    return bool(value)


# The Ansible filters these templates and expressions use. Each takes the same
# arguments in the same order as Ansible's for the calls made here.
env.filters["regex_replace"] = lambda value, pattern, repl="": re.sub(
    pattern, repl, value)
env.filters["extract"] = lambda key, container: container[key]
env.filters["bool"] = ansible_bool


def role_file(role, kind):
    path = REPO / "roles" / role / kind / "main.yaml"
    return yaml.safe_load(path.read_text()) or {}


def role_defaults(role):
    return role_file(role, "defaults")


def evaluate(expression, context):
    """Resolve one role variable, which is itself a Jinja expression.

    Ansible hands back the value a whole-template expression evaluates to, not
    its text, so a list stays a list and a boolean stays a boolean. literal_eval
    reproduces that; anything that is not a Python literal is left as the string
    it rendered to.
    """
    rendered = env.from_string(expression).render(context).strip()
    try:
        return ast.literal_eval(rendered)
    except (ValueError, SyntaxError):
        return rendered


def context_for(pooled):
    """Everything setup_haproxy would have in scope, from the roles themselves.

    Reading the roles rather than restating them is deliberate: a change to the
    connection budget, to a port, or to how the pooled server list is derived
    shows up in the fixtures, where it can be reviewed, instead of being
    papered over by a second copy of the values that lives here.
    """
    haproxy = role_defaults("setup_haproxy")
    shared = role_defaults("role_config")
    derived = role_file("role_config", "vars")

    context = {
        "nodes_in_zone": NODES,
        # Hostvars carry only what the template and the derived vars read.
        # Attribute lookups that miss -- pgbouncer_max_client_conn below --
        # fall through to the default, which is what an inventory that
        # overrides nothing does.
        "hostvars": {node: {"inventory_hostname": node,
                            "pgbouncer_enabled": pooled} for node in NODES},
        "groups": {"pgedge": NODES},
        "haproxy_extra_routes": haproxy["haproxy_extra_routes"],
        "pg_port": shared["pg_port"],
        "proxy_port": shared["proxy_port"],
        "pooler_port": shared["pooler_port"],
        "pgbouncer_port": shared["pgbouncer_port"],
        "pgbouncer_max_client_conn": shared["pgbouncer_max_client_conn"],
    }

    # Derived exactly as role_config derives them: whether the cluster pools is
    # read out of the nodes' own hostvars, because a proxy host does not carry
    # pgbouncer_enabled itself, and the pooled server list follows from it.
    context["cluster_is_pooled"] = evaluate(
        derived["cluster_is_pooled"], context)
    context["pooled_nodes_in_zone"] = evaluate(
        derived["pooled_nodes_in_zone"], context)

    # Only defined where the cluster pools, as in a real run: the expression
    # indexes hostvars by the zone's first node, so an unpooled cluster must
    # never reach it. Ansible resolves variables lazily and so does the
    # conditional in haproxy_max_conn below; leaving this out of the unpooled
    # context proves that path does not need it.
    if context["pooled_nodes_in_zone"]:
        context["haproxy_pooler_max_conn"] = evaluate(
            haproxy["haproxy_pooler_max_conn"], context)

    context["haproxy_max_conn"] = evaluate(haproxy["haproxy_max_conn"], context)
    return context


def render(pooled):
    return env.from_string(TEMPLATE.read_text()).render(context_for(pooled))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true",
                        help="rewrite the fixtures from the current template")
    args = parser.parse_args()

    failures = 0
    for name, pooled in CASES.items():
        fixture = FIXTURES / name
        rendered = render(pooled)

        if args.update:
            fixture.write_text(rendered)
            print(f"updated {fixture.relative_to(REPO)}")
            continue

        expected = fixture.read_text()
        if rendered == expected:
            print(f"ok       {fixture.relative_to(REPO)}")
            continue

        failures += 1
        print(f"CHANGED  {fixture.relative_to(REPO)}")
        sys.stdout.writelines(difflib.unified_diff(
            expected.splitlines(True), rendered.splitlines(True),
            str(fixture.relative_to(REPO)), "rendered"))

    if failures:
        print(f"\n{failures} render(s) no longer match. Deploying this would "
              f"change haproxy.cfg on hosts the change was not meant for; if "
              f"it was meant, re-run with --update and commit the fixture.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
