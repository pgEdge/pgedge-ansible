#!/bin/bash
# Exercise a recovery against a cluster that is already deployed and running
# (checklist: recovery coverage).
#
#   tests/run-test.sh ultra-ha rocky9 --keep     # deploy, leave containers up
#   tests/run-recovery-test.sh ultra-ha rocky9   # seed, wipe, recover, commit
#
# Split from run-test.sh on purpose. Recovery starts by wiping the cluster, so
# it runs last and separately, and keeping it a second command means a failed
# recovery leaves the wreckage in place to look at rather than taking the
# deployment down with it.
#
# Run this as many times as it takes. Each attempt wipes whatever state the
# previous one left and rebuilds from the repository, so a failed attempt is
# not something to clean up before the next one. The deployment is the
# expensive half and it is not repeated: one run-test.sh gives you a cluster
# with backups, and every attempt after that restores from those same backups.
#
# Only the HA scenario can be recovered. A cluster without Patroni must be
# restored with pgbackrest directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <scenario> <os> [dcs] [backup] [-- extra ansible args...]"
  echo "  scenario: ultra-ha (the only recoverable scenario)"
  echo "  os:       debian12 | rocky9"
  echo "  dcs:      etcd3 (default) | consul"
  echo "  backup:   ssh (default) | s3 -- as the deployment was given"
  echo ""
  echo "Deploy first with:"
  echo "  tests/run-test.sh <scenario> <os> [dcs] [backup] --keep"
  echo ""
  echo "Point-in-time recovery instead of latest:"
  echo "  $0 ultra-ha rocky9 -- -e recovery_target_type=time \\"
  echo "     -e \"recovery_target='2026-09-16 18:00:00+00'\""
  exit 1
}

SCENARIO="${1:-}"
OS="${2:-}"
DCS="etcd3"
BACKUP="ssh"

[ -z "$SCENARIO" ] || [ -z "$OS" ] && usage

if [ "$SCENARIO" != "ultra-ha" ]; then
  echo "ERROR: only ultra-ha can be recovered; '$SCENARIO' has no Patroni."
  exit 1
fi

# The DCS and the backup type are told apart by value, as run-test.sh does, so
# either can be given without the other.
shift 2
while [ -n "${1:-}" ] && [ "$1" != "--" ]; do
  case "$1" in
    ssh|s3) BACKUP="$1" ;;
    *) DCS="$1" ;;
  esac
  shift
done
[ "${1:-}" = "--" ] && shift
EXTRA_ARGS=("$@")

INVENTORY="$SCRIPT_DIR/inventories/${SCENARIO}.yml"
# Where the deployment staged its TLS material, which the recovery reuses. It is
# the directory the deployment playbook lives in, because Ansible resolves those
# relative paths against the playbook's own location -- and that differs between
# a local run (sample-playbooks/<scenario>/) and CI (tests/playbooks/). The
# workflow sets DEPLOY_PLAYBOOK_DIR accordingly.
DEPLOY_DIR="${DEPLOY_PLAYBOOK_DIR:-$PROJECT_DIR/sample-playbooks/${SCENARIO}}"
RECOVER_DIR="$PROJECT_DIR/sample-playbooks/${SCENARIO}-recover"
WIPE_PLAYBOOK="$PROJECT_DIR/sample-playbooks/wipe-cluster/playbook.yaml"
KEY="$SCRIPT_DIR/.ssh/id_ed25519"

# Under CI the deployment ran moments ago in the same job, so the leniency below
# for a cluster a previous attempt left mid-recovery has nothing to forgive: a
# cluster that cannot be seeded, or a deployment that staged no TLS, is the
# deployment failing, and a recovery run on top of it would prove nothing.
# GitHub Actions and act both set CI.
IN_CI=false
[ "${CI:-}" = "true" ] && IN_CI=true

EXTRA_VARS=()
if [ "$DCS" != "etcd3" ]; then
  EXTRA_VARS+=(-e "@$SCRIPT_DIR/vars/dcs-${DCS}.yml")
fi

# The repository the deployment used, layered on the same way run-test.sh
# layers it. The S3 store's CA is already on the nodes from the deployment.
INVENTORY_ARGS=(-i "$INVENTORY")
case "$BACKUP" in
  ssh) INVENTORY_ARGS+=(-i "$SCRIPT_DIR/inventories/${SCENARIO}-ssh.yml") ;;
  s3) EXTRA_VARS+=(-e "@$SCRIPT_DIR/vars/backup-s3.yml") ;;
  *) echo "ERROR: unknown backup type: $BACKUP"; usage ;;
esac

# The node to restore from its repository: the first pgEdge node the inventory
# lists, which is the first node of its zone and so the one the role requires.
# Asked of Ansible rather than scraped out of the YAML, because the 'haproxy'
# and 'backup' groups list addresses at the same indentation and a text match
# picks whichever appears first in the file.
RECOVERY_NODE="$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" \
  ansible-inventory "${INVENTORY_ARGS[@]}" --list |
  python3 -c "import json,sys; print(json.load(sys.stdin)['pgedge']['hosts'][0])")"

if [ -z "$RECOVERY_NODE" ]; then
  echo "ERROR: could not determine the first pgEdge node from $INVENTORY"
  exit 1
fi

echo "==> Recovering ${SCENARIO} on ${OS} (dcs=${DCS}, backup=${BACKUP})" \
  "from ${RECOVERY_NODE}"

# Offline, and first: the templates are rendered after the cluster has been
# wiped, and one that cannot render is much cheaper to find out about here.
echo "==> Step 0: Checking rendered templates..."
python3 "$SCRIPT_DIR/render/check-patroni.py"
python3 "$SCRIPT_DIR/render/check-pgbackrest.py"

# Build and install the collection, exactly as run-test.sh does.
#
# Not optional, and not merely tidy. The playbooks reach these roles through the
# collection, so Ansible runs whatever is installed under
# ~/.ansible/collections -- not the working tree. Without this step a recovery
# re-runs the roles the last deployment installed, which means every edit made
# while iterating on the recipe is silently ignored and the same failure repeats
# from code that is no longer on disk. That cost two full cycles before anyone
# noticed the task name in the error had already been renamed.
#
# Clean first, too: a dirty tree keeps one version string across edits, so the
# tarball from the last build carries the same name as the one this tree would
# produce, and only a rebuild guarantees it holds what is on disk.
echo "==> Step 0b: Building and installing the collection from this tree..."
( cd "$PROJECT_DIR" && make clean install )

echo "    Installed recover_postgres tasks now in use:"
sed -n 's/^- name: /      /p' \
  ~/.ansible/collections/ansible_collections/pgedge/platform/roles/recover_postgres/tasks/restore.yaml \
  2>/dev/null | head -4 || true

run() {
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
    "$1" "${INVENTORY_ARGS[@]}" --private-key "$KEY" "${@:2}"
}

# Step 1: put data in the cluster that only a restore can bring back -- once.
#
# The marker rows need writing exactly once. From then on they live in archived
# WAL, so every later attempt restores them again, and re-seeding would add
# nothing. It also could not: a cluster left mid-recovery by a failed attempt
# may have no working zone to write them to, and needs none, because the
# repository already holds everything the next attempt reads.
#
# So seed when there is a cluster to seed, and otherwise carry straight on.
echo "==> Step 1: Checking whether there is a cluster to seed..."
if ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible pgedge \
     "${INVENTORY_ARGS[@]}" --private-key "$KEY" -b --become-user postgres \
     -m command -a "psql -d postgres -t -A -c 'SELECT 1'" >/dev/null 2>&1; then
  echo "    Cluster is up; seeding data that exists only in archived WAL."
  run "$SCRIPT_DIR/playbooks/seed-recovery.yml" "${EXTRA_VARS[@]}"
elif $IN_CI; then
  echo "ERROR: no working cluster to seed. Under CI the deployment ran just"
  echo "       before this, so there is no earlier attempt to have left it"
  echo "       mid-recovery, and without the marker rows the verification has"
  echo "       nothing to find."
  exit 1
else
  echo "    No working cluster, so nothing to seed -- carrying on."
  echo "    A previous attempt left this cluster wiped or partly recovered. The"
  echo "    marker rows are already in archived WAL from when it was seeded, and"
  echo "    that is what this attempt restores; seeding is a one-time step, not"
  echo "    a per-attempt one."
  echo "    If this is the first attempt against a freshly deployed cluster,"
  echo "    then that deployment is not running and is worth looking at before"
  echo "    going further."
fi

# Step 2: setup_postgres stages its TLS material from a directory Ansible
# resolves against the playbook's own location, and recover_postgres applies
# that role to every node. Without the deployment's
# staging directory it would mint a fresh self-signed certificate for those
# zones, leaving the cluster with two. Reuse the one the deployment made, the
# same way check-idempotence.sh reuses it for the pooler.
#
# All but the etcd certificate authority. That is handed to the recovery the
# way a production inventory would hand it over -- etcd_ca_cert and etcd_ca_key
# -- so this run exercises the inventory-supplied path rather than a staged
# copy, which the deployment itself already covers. The staged copy an earlier
# attempt left is removed first, or every attempt after the first would only
# compare against it rather than write it.
echo "==> Step 2: Reusing the deployment's TLS staging directory..."
if [ -d "$DEPLOY_DIR/tls" ]; then
  mkdir -p "$RECOVER_DIR"
  cp -r "$DEPLOY_DIR/tls" "$RECOVER_DIR/"
  rm -rf "$RECOVER_DIR/tls/etcd"
  if [ -f "$DEPLOY_DIR/tls/etcd/ca.crt" ]; then
    CA_VARS="$(mktemp)"
    trap 'rm -f "$CA_VARS"' EXIT
    python3 - "$DEPLOY_DIR/tls/etcd" "$CA_VARS" <<'PY'
import json, pathlib, sys
src = pathlib.Path(sys.argv[1])
pathlib.Path(sys.argv[2]).write_text(json.dumps({
    "etcd_ca_cert": (src / "ca.crt").read_text(),
    "etcd_ca_key": (src / "ca.key").read_text(),
}))
PY
    echo "    Supplying the etcd certificate authority as etcd_ca_cert/etcd_ca_key."
    EXTRA_VARS+=(-e "@$CA_VARS")
  fi
elif $IN_CI; then
  echo "ERROR: no TLS staging at $DEPLOY_DIR/tls. The deployment in this job"
  echo "       should have left it there; check DEPLOY_PLAYBOOK_DIR."
  exit 1
else
  echo "    WARNING: no TLS staging at $DEPLOY_DIR/tls; rebuilt zones will get"
  echo "             a freshly generated certificate."
fi

# Step 3: tear the cluster down. Every backup is left where it is; this is what
# an operator runs first, whether the hosts are being reused or a previous
# attempt went wrong. The moment is noted so the verification can tell any
# backup taken from here on, which the recovery must not take.
echo "==> Step 3: Wiping the cluster..."
RECOVERY_STARTED="$(date +%s)"
run "$WIPE_PLAYBOOK" \
  -e wipe_confirm=true \
  "${EXTRA_VARS[@]}"

# Step 4: the recovery itself.
echo "==> Step 4: Running the recovery playbook..."
run "$RECOVER_DIR/playbook.yaml" \
  -e recovery_node="$RECOVERY_NODE" \
  "${EXTRA_VARS[@]}" \
  "${EXTRA_ARGS[@]}" \
  -v

# Step 5: did the data come back, is the cluster whole, and did the recovery
# leave every backup it could have restored from?
echo "==> Step 5: Verifying the recovered cluster..."
run "$SCRIPT_DIR/verify/verify-recovery.yml" \
  -e recovery_started="$RECOVERY_STARTED" \
  "${EXTRA_VARS[@]}" \
  "${EXTRA_ARGS[@]}" \
  -v

# Step 6: commit to it, which takes the backups the recovery did not.
#
# The recovery's own arguments go to the verification: whether it stopped at a
# point-in-time target decides whether the restored zone had to take one.
echo "==> Step 6: Committing the recovery..."
run "$RECOVER_DIR/commit-restore.yaml" "${EXTRA_VARS[@]}"

echo "==> Step 7: Verifying the committed backups..."
run "$SCRIPT_DIR/verify/verify-commit.yml" \
  "${EXTRA_VARS[@]}" \
  "${EXTRA_ARGS[@]}" \
  -v

echo ""
echo "========================================="
echo "  RECOVERY TEST PASSED: ${SCENARIO} on ${OS}"
echo "========================================="
