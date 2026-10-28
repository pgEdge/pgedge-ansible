#!/bin/bash
# Check a cluster deployed with repo_url used the site's repository: re-applying
# install_repos changes nothing, nothing still points at pgEdge's own servers,
# and the packages themselves came through the proxy from
# tests/compose/repo-proxy.yml.
#
#   tests/check-repo.sh <compose project> <compose args...> -- <ansible args...>
#
# The compose arguments are the -f files the containers were started with. The
# ansible arguments are the inventory, connection options and variables the
# deployment used, -e @tests/vars/repo-*.yml among them.
#
# Run after the deployment, before anything else re-applies install_repos.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PROJECT="${1:-}"
[ -n "$PROJECT" ] || {
  echo "Usage: $0 <compose project> <compose args...> -- <ansible args...>"
  exit 1
}
shift

COMPOSE_ARGS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  COMPOSE_ARGS+=("$1")
  shift
done
[ "${1:-}" = "--" ] && shift
ANSIBLE_ARGS=("$@")

echo "==> Re-applying install_repos..."
OUTPUT=$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$SCRIPT_DIR/playbooks/repo-reapply.yml" "${ANSIBLE_ARGS[@]}" 2>&1) ||
  { echo "$OUTPUT"; exit 1; }
echo "$OUTPUT"
if echo "$OUTPUT" | grep -qE 'changed=[1-9]'; then
  echo "ERROR: re-applying install_repos changed something"
  exit 1
fi

echo "==> Checking nothing points at pgEdge's own servers..."
ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$SCRIPT_DIR/verify/verify-repo.yml" "${ANSIBLE_ARGS[@]}" -v

# The packages themselves, not just the metadata, came through the proxy.
echo "==> Checking packages came through the site's repository..."
PACKAGES=$(docker compose -p "$PROJECT" "${COMPOSE_ARGS[@]}" logs repo |
  grep -cE '"GET [^ ]+\.(rpm|deb) HTTP/[0-9.]+" 200' || true)
if [ "$PACKAGES" -eq 0 ]; then
  echo "ERROR: no package was downloaded through the site's repository"
  exit 1
fi
echo "    $PACKAGES packages were downloaded through the site's repository"
