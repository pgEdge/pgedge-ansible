#!/bin/bash
# Re-apply the pooler roles and fail if any task reports a change (checklist
# §8.8). Run after a deployment has finished, against the same inventory.
#
#   tests/check-idempotence.sh <inventory> <deployment-playbook> [args...]
#
# The deployment playbook is named only for the directory it lives in: the
# pooler's certificate is staged from the controller, from a path Ansible
# resolves against the playbook's own directory, and that directory differs
# between a local run (sample-playbooks/<scenario>/) and CI
# (tests/playbooks/). Pointing at the same certificate the deployment used is
# what keeps this a test of idempotence rather than of file layout.
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

STAGING_DIR="$(cd "$(dirname "$DEPLOY_PLAYBOOK")" && pwd)/tls/postgres"

OUTPUT=$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$SCRIPT_DIR/playbooks/pgbouncer-idempotence.yml" \
  -i "$INVENTORY" \
  -e "pgbouncer_tls_cert_source=$STAGING_DIR/server.crt" \
  -e "pgbouncer_tls_key_source=$STAGING_DIR/server.key" \
  "$@" 2>&1) || { echo "$OUTPUT"; exit 1; }

echo "$OUTPUT"

if echo "$OUTPUT" | grep -qE 'changed=[1-9]'; then
  echo ""
  echo "ERROR: re-applying the pooler roles changed something. Every file"
  echo "       setup_pgbouncer writes feeds its restart condition, so a task"
  echo "       that reports a change it did not make restarts the pooled"
  echo "       endpoint on every run."
  exit 1
fi

echo ""
echo "    Pooler roles are idempotent: no host reported a change."
