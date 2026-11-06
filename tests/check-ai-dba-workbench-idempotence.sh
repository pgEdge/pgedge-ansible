#!/bin/bash
# Re-apply the AI DBA Workbench's roles and fail if any task reports a change.
# Run after a deployment with an ai_dba_workbench host has finished, against
# the same inventory.
#
#   tests/check-ai-dba-workbench-idempotence.sh <inventory> <deploy-playbook> \
#     [args...]
#
# The deployment playbook is named only for the directory it lives in: the web
# client's self-signed certificate is generated on the controller, from a path
# Ansible resolves against the playbook's own directory, and that directory
# differs between a local run (sample-playbooks/<scenario>-ai-dba-workbench/)
# and CI (tests/playbooks/). Pointing at the certificate the deployment used is
# what keeps this a test of idempotence rather than of file layout.
#
# Any further arguments -- -i, --private-key, -e ... -- are passed through.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INVENTORY="${1:-}"
DEPLOY_PLAYBOOK="${2:-}"

if [ -z "$INVENTORY" ] || [ -z "$DEPLOY_PLAYBOOK" ]; then
  echo "Usage: $0 <inventory> <deployment-playbook> [ansible-playbook args...]"
  exit 1
fi

shift 2

STAGING_DIR="$(cd "$(dirname "$DEPLOY_PLAYBOOK")" && pwd)/tls/ai-dba-workbench"

OUTPUT=$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$SCRIPT_DIR/playbooks/ai-dba-workbench-idempotence.yml" \
  -i "$INVENTORY" \
  -e "ai_dba_workbench_tls_staging_dir=$STAGING_DIR" \
  "$@" 2>&1) || { echo "$OUTPUT"; exit 1; }

echo "$OUTPUT"

if echo "$OUTPUT" | grep -qE 'changed=[1-9]'; then
  echo ""
  echo "ERROR: re-applying the AI DBA Workbench roles changed something."
  echo "       Each file setup_ai_dba_workbench writes feeds a service's"
  echo "       restart condition, and each record it sends the Workbench is"
  echo "       sent only where it differs, so a task that reports a change it"
  echo "       did not make restarts a service or rewrites a record on every"
  echo "       run."
  exit 1
fi

echo ""
echo "    AI DBA Workbench roles are idempotent: no host reported a change."
