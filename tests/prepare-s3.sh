#!/bin/bash
# Wait for the MinIO container from tests/compose/backup-s3.yml to be serving
# its bucket, then give every pgEdge node the certificate authority it was
# signed with, at the path tests/vars/backup-s3.yml names as storage_ca_file.
#
#   tests/prepare-s3.sh <compose project> <compose args...> -- <ansible args...>
#
# The compose arguments are the -f files the containers were started with. The
# ansible arguments are the inventory and connection options the deployment
# uses, so the CA reaches exactly the nodes the playbook will configure.
#
# Run after the nodes accept SSH and before the deployment. The first thing
# that talks to the repository is setup_postgres's identity check, and that one
# is allowed to skip a repository it cannot read -- so a CA that arrived late
# would not fail there, but at the very end, in finalize_backrest.
#
# The CA is read out of the container rather than generated here because under
# act the checkout lives in the job container: a file written there and bind
# mounted into MinIO would resolve against a host path that does not exist.

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

CA_DIR="$SCRIPT_DIR/.s3"
CA_FILE="$CA_DIR/ca.crt"
CA_DEST="$(python3 -c "
import sys, yaml
params = yaml.safe_load(open(sys.argv[1]))['backup_repo_params']
print(params['storage_ca_file'])
" "$SCRIPT_DIR/vars/backup-s3.yml")"

compose() {
  docker compose -p "$PROJECT" "${COMPOSE_ARGS[@]}" "$@"
}

echo "==> Waiting for MinIO to serve its bucket..."
ELAPSED=0
until compose exec -T minio test -f /tmp/s3-ready 2>/dev/null; do
  ELAPSED=$((ELAPSED + 2))
  if [ $ELAPSED -ge 120 ]; then
    echo "ERROR: MinIO did not create its bucket within 120s"
    compose logs minio || true
    exit 1
  fi
  sleep 2
done
echo "    MinIO is ready"

echo "==> Copying MinIO's certificate authority to the pgEdge nodes..."
mkdir -p "$CA_DIR"
compose exec -T minio cat /certs/ca.crt > "$CA_FILE"
grep -q "BEGIN CERTIFICATE" "$CA_FILE" || {
  echo "ERROR: $CA_FILE does not hold a certificate"
  exit 1
}

nodes() {
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible pgedge -b \
    "${ANSIBLE_ARGS[@]}" "$@"
}

nodes -m ansible.builtin.file \
  -a "path=$(dirname "$CA_DEST") state=directory mode=0755"
nodes -m ansible.builtin.copy -a "src=$CA_FILE dest=$CA_DEST mode=0644"
echo "    CA installed at $CA_DEST"
