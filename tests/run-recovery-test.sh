#!/bin/bash
# Exercise the recovery role against a cluster that is already deployed and
# running (checklist: recovery coverage).
#
#   tests/run-test.sh ultra-ha rocky9 --keep     # deploy, leave containers up
#   tests/run-recovery-test.sh ultra-ha rocky9   # seed, recover, verify
#
# Split from run-test.sh on purpose. Recovery destroys every data directory in
# the cluster, so it runs last and separately, and keeping it a second command
# means a failed recovery leaves the wreckage in place to look at rather than
# taking the deployment down with it.
#
# Run this as many times as it takes. The recovery erases and rebuilds from the
# repository whatever state the previous attempt left, so a failed attempt is
# not something to clean up before the next one -- it is the starting state the
# next one expects. The deployment is the expensive half and it is not repeated:
# one run-test.sh gives you a cluster with backups, and every attempt after that
# restores from those same backups.
#
# Only the HA scenario can be recovered. A cluster without Patroni has no
# bootstrap method to restore through and must be restored with pgbackrest
# directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <scenario> <os> [dcs] [-- extra ansible args...]"
  echo "  scenario: ultra-ha (the only recoverable scenario)"
  echo "  os:       debian12 | rocky9"
  echo "  dcs:      etcd3 (default) | consul"
  echo ""
  echo "Deploy first with: tests/run-test.sh <scenario> <os> [dcs] --keep"
  echo ""
  echo "Point-in-time recovery instead of latest:"
  echo "  $0 ultra-ha rocky9 -- -e recovery_target_type=time \\"
  echo "     -e 'recovery_target=2026-09-16 18:00:00+00'"
  exit 1
}

SCENARIO="${1:-}"
OS="${2:-}"
DCS="etcd3"

[ -z "$SCENARIO" ] || [ -z "$OS" ] && usage

if [ "$SCENARIO" != "ultra-ha" ]; then
  echo "ERROR: only ultra-ha can be recovered; '$SCENARIO' has no Patroni."
  exit 1
fi

shift 2
if [ "${1:-}" != "--" ] && [ -n "${1:-}" ]; then
  DCS="$1"
  shift
fi
[ "${1:-}" = "--" ] && shift
EXTRA_ARGS=("$@")

INVENTORY="$SCRIPT_DIR/inventories/${SCENARIO}.yml"
# Where the deployment staged its TLS material, which the recovery reuses. It is
# the directory the deployment playbook lives in, because Ansible resolves those
# relative paths against the playbook's own location -- and that differs between
# a local run (sample-playbooks/<scenario>/) and CI (tests/playbooks/). The
# workflow sets DEPLOY_PLAYBOOK_DIR accordingly.
DEPLOY_DIR="${DEPLOY_PLAYBOOK_DIR:-$PROJECT_DIR/sample-playbooks/${SCENARIO}}"
RECOVER_DIR="$PROJECT_DIR/sample-playbooks/recover-cluster"
KEY="$SCRIPT_DIR/.ssh/id_ed25519"

EXTRA_VARS=()
if [ "$DCS" != "etcd3" ]; then
  EXTRA_VARS+=(-e "@$SCRIPT_DIR/vars/dcs-${DCS}.yml")
fi

# The node to restore from its repository: the first pgEdge node the inventory
# lists, which is the first node of its zone and so the one the role requires.
# Asked of Ansible rather than scraped out of the YAML, because the 'haproxy'
# and 'backup' groups list addresses at the same indentation and a text match
# picks whichever appears first in the file.
RECOVERY_NODE="$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" \
  ansible-inventory -i "$INVENTORY" --list |
  python3 -c "import json,sys; print(json.load(sys.stdin)['pgedge']['hosts'][0])")"

if [ -z "$RECOVERY_NODE" ]; then
  echo "ERROR: could not determine the first pgEdge node from $INVENTORY"
  exit 1
fi

echo "==> Recovering ${SCENARIO} on ${OS} (dcs=${DCS}) from ${RECOVERY_NODE}"

# Offline, and first: the Patroni template is re-rendered on the restored node
# partway through a recovery, after the cluster has been erased. A template that
# cannot render is much cheaper to find out about here.
echo "==> Step 0: Checking rendered templates..."
python3 "$SCRIPT_DIR/render/check-patroni.py"

# Build and install the collection, exactly as run-test.sh does.
#
# Not optional, and not merely tidy. The playbooks reach these roles through the
# collection, so Ansible runs whatever is installed under
# ~/.ansible/collections -- not the working tree. Without this step a recovery
# re-runs the roles the last deployment installed, which means every edit made
# while iterating on the recipe is silently ignored and the same failure repeats
# from code that is no longer on disk. That cost two full cycles before anyone
# noticed the task name in the error had already been renamed.
echo "==> Step 0b: Building and installing the collection from this tree..."
( cd "$PROJECT_DIR" && make install )

echo "    Installed recover_cluster tasks now in use:"
sed -n 's/^  - name: /      /p' \
  ~/.ansible/collections/ansible_collections/pgedge/platform/roles/recover_cluster/tasks/clean_spock.yaml \
  2>/dev/null | head -4 || true

run() {
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
    "$1" -i "$INVENTORY" --private-key "$KEY" "${@:2}"
}

# Step 1: put data in the cluster that only a restore can bring back -- once.
#
# The marker rows need writing exactly once. From then on they live in archived
# WAL, so every later attempt restores them again, and re-seeding would add
# nothing. It also could not: a cluster left mid-recovery by a failed attempt
# has no working zone to write them to, and needs none, because the repository
# already holds everything the next attempt reads.
#
# So seed when there is a cluster to seed, and otherwise carry straight on.
echo "==> Step 1: Checking whether there is a cluster to seed..."
if ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible pgedge \
     -i "$INVENTORY" --private-key "$KEY" -b --become-user postgres \
     -m command -a "psql -d postgres -t -A -c 'SELECT 1'" >/dev/null 2>&1; then
  echo "    Cluster is up; seeding data that exists only in archived WAL."
  run "$SCRIPT_DIR/playbooks/seed-recovery.yml" "${EXTRA_VARS[@]}"
else
  echo "    No working cluster, so nothing to seed -- carrying on."
  echo "    A previous attempt left this cluster mid-recovery. The marker rows"
  echo "    are already in archived WAL from when it was seeded, and that is"
  echo "    what this attempt restores; seeding is a one-time step, not a"
  echo "    per-attempt one."
  echo "    If this is the first attempt against a freshly deployed cluster,"
  echo "    then that deployment is not running and is worth looking at before"
  echo "    going further."
fi

# Step 2: setup_postgres stages its TLS material from a directory Ansible
# resolves against the playbook's own location, and the recovery rebuilds the
# zones that were not restored by applying that role. Without the deployment's
# staging directory it would mint a fresh self-signed certificate for those
# zones, leaving the cluster with two. Reuse the one the deployment made, the
# same way check-idempotence.sh reuses it for the pooler.
echo "==> Step 2: Reusing the deployment's TLS staging directory..."
if [ -d "$DEPLOY_DIR/tls" ]; then
  mkdir -p "$RECOVER_DIR"
  cp -r "$DEPLOY_DIR/tls" "$RECOVER_DIR/"
else
  echo "    WARNING: no TLS staging at $DEPLOY_DIR/tls; rebuilt zones will get"
  echo "             a freshly generated certificate."
fi

# Step 3: the recovery itself.
echo "==> Step 3: Running the recovery playbook..."
run "$RECOVER_DIR/playbook.yaml" \
  -e recovery_node="$RECOVERY_NODE" \
  -e recovery_confirm=true \
  "${EXTRA_VARS[@]}" \
  "${EXTRA_ARGS[@]}" \
  -v

# Step 4: did the data come back, and is the cluster whole?
echo "==> Step 4: Verifying the recovered cluster..."
run "$SCRIPT_DIR/verify/verify-recovery.yml" "${EXTRA_VARS[@]}" -v

echo ""
echo "========================================="
echo "  RECOVERY TEST PASSED: ${SCENARIO} on ${OS}"
echo "========================================="
