#!/bin/bash
# Run the deployment playbook again and fail if any task reports a change.
# Run after a deployment has finished, against the same inventory.
#
#   tests/check-idempotence.sh <inventory> <deployment-playbook> [args...]
#
# A deployed cluster is exactly what the playbook describes, so running it a
# second time has nothing to do. A task that reports a change anyway either
# did something it should not have -- a restart, a reload, a rewritten file --
# or claims a change it did not make, which hides the real ones from anyone
# reading the recap. Both fail this check.
#
# The playbook is run from where it lives, as the deployment ran it: the
# certificates the deployment staged are found relative to the playbook's own
# directory, and a run from anywhere else would stage new ones.
#
# Only the tasks that changed something are printed, under their headers, so
# a failure shows what to look at rather than the whole run.
#
# Any further arguments -- --private-key, -e ... -- are passed through.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INVENTORY="${1:-}"
DEPLOY_PLAYBOOK="${2:-}"

if [ -z "$INVENTORY" ] || [ -z "$DEPLOY_PLAYBOOK" ]; then
  echo "Usage: $0 <inventory> <deployment-playbook> [ansible-playbook args...]"
  exit 1
fi

shift 2

OUTPUT=$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" \
  ANSIBLE_DISPLAY_OK_HOSTS=false \
  ANSIBLE_DISPLAY_SKIPPED_HOSTS=false \
  ansible-playbook \
  "$DEPLOY_PLAYBOOK" \
  -i "$INVENTORY" \
  "$@" 2>&1) || { echo "$OUTPUT"; exit 1; }

echo "$OUTPUT"

if echo "$OUTPUT" | grep -qE 'changed=[1-9]'; then
  echo ""
  echo "ERROR: running the deployment playbook again changed something. Each"
  echo "       task listed above with a 'changed' result either did work a"
  echo "       deployed cluster did not need, or reports a change it did not"
  echo "       make."
  exit 1
fi

echo ""
echo "    The deployment is idempotent: no host reported a change."
