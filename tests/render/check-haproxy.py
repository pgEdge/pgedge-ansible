#!/usr/bin/env python3
"""Render setup_haproxy's template offline and compare it against fixtures.

Pooling is additive: a cluster with no node in the 'pgbouncer' group must get
exactly the haproxy.cfg it got before the pooler existed. The live matrix
cannot observe that -- every zone in it pools -- so the invariant is checked
here instead, against expected/haproxy-unpooled.cfg, which was captured by
rendering the template as it stood on main before the pooled listener was
added. The pooled fixture beside it is the counterpart: it holds the output a
zone with pooled nodes should get, so a change to that listener has to be
looked at rather than merely deployed.

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

# One zone of a cluster, of which the first two nodes pool. Addresses rather
# than names, as the test inventories use, and a third unpooled node so the
# pooled listener's server list is visibly not the direct listener's.
NODES = ["192.168.6.10", "192.168.6.11", "192.168.6.12"]
POOLED = NODES[:2]

CASES = {
    "haproxy-unpooled.cfg": [],
    "haproxy-pooled.cfg": POOLED,
}

env = Environment(trim_blocks=True, keep_trailing_newline=True,
                  undefined=StrictUndefined)
# The one Ansible filter the template uses. Ansible's version takes the same
# arguments in the same order for this call.
env.filters["regex_replace"] = lambda value, pattern, repl="": re.sub(
    pattern, repl, value)


def role_defaults(role):
    path = REPO / "roles" / role / "defaults" / "main.yaml"
    return yaml.safe_load(path.read_text()) or {}


def evaluate(expression, context):
    """Resolve one role default, which is itself a Jinja expression."""
    return env.from_string(expression).render(context).strip()


def context_for(pooled):
    """Everything setup_haproxy would have in scope, from the roles themselves.

    Reading the defaults rather than restating them is deliberate: a change to
    the connection budget or to a port shows up in the fixtures, where it can
    be reviewed, instead of being papered over by a second copy of the values
    that lives here.
    """
    haproxy = role_defaults("setup_haproxy")
    shared = role_defaults("role_config")

    context = {
        "nodes_in_zone": NODES,
        "pooled_nodes_in_zone": pooled,
        # Hostvars carry only what the template reads. Attribute lookups that
        # miss -- pgbouncer_max_client_conn below -- fall through to the
        # default, which is what an inventory that overrides nothing does.
        "hostvars": {node: {"inventory_hostname": node} for node in NODES},
        "haproxy_extra_routes": haproxy["haproxy_extra_routes"],
        "pg_port": shared["pg_port"],
        "proxy_port": shared["proxy_port"],
        "pooler_port": shared["pooler_port"],
        "pgbouncer_port": shared["pgbouncer_port"],
        "pgbouncer_max_client_conn": shared["pgbouncer_max_client_conn"],
    }

    # Only defined where the zone pools, as in a real run: the expression
    # indexes hostvars by the first pooled node, so an unpooled zone must never
    # reach it. Ansible resolves variables lazily and so does the conditional
    # in haproxy_max_conn below; leaving this out of the unpooled context
    # proves that path does not need it.
    if pooled:
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
