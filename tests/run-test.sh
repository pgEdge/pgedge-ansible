#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <scenario> <os> [dcs] [--keep]"
  echo "  scenario: simple-cluster | ultra-ha"
  echo "  os:       debian12 | rocky9"
  echo "  dcs:      etcd3 (default) | consul"
  echo "  --keep:   don't tear down containers after test"
  exit 1
}

SCENARIO="${1:-}"
OS="${2:-}"
DCS="etcd3"
KEEP=false

if [ -n "${3:-}" ] && [ "$3" != "--keep" ]; then
  DCS="$3"
fi

for arg in "$@"; do
  if [ "$arg" = "--keep" ]; then
    KEEP=true
  fi
done

if [ -z "$SCENARIO" ] || [ -z "$OS" ]; then
  usage
fi

COMPOSE_FILE="$SCRIPT_DIR/compose/${SCENARIO}-${OS}.yml"
INVENTORY="$SCRIPT_DIR/inventories/${SCENARIO}.yml"
PLAYBOOK="$PROJECT_DIR/sample-playbooks/${SCENARIO}/playbook.yaml"
VERIFY_PLAYBOOK="$SCRIPT_DIR/verify/verify-${SCENARIO}.yml"
PROJECT_NAME="pgedge-test-${SCENARIO}-${OS}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: Compose file not found: $COMPOSE_FILE"
  exit 1
fi

if [ ! -f "$INVENTORY" ]; then
  echo "ERROR: Inventory not found: $INVENTORY"
  exit 1
fi

if [ ! -f "$PLAYBOOK" ]; then
  echo "ERROR: Playbook not found: $PLAYBOOK"
  exit 1
fi

COMPOSE_ARGS=(-f "$COMPOSE_FILE")
EXTRA_VARS=()

if [ "$DCS" != "etcd3" ]; then
  DCS_COMPOSE="$SCRIPT_DIR/compose/dcs-${DCS}.yml"
  DCS_VARS="$SCRIPT_DIR/vars/dcs-${DCS}.yml"

  if [ ! -f "$DCS_COMPOSE" ]; then
    echo "ERROR: DCS compose overlay not found: $DCS_COMPOSE"
    exit 1
  fi

  if [ ! -f "$DCS_VARS" ]; then
    echo "ERROR: DCS variable file not found: $DCS_VARS"
    exit 1
  fi

  COMPOSE_ARGS+=(-f "$DCS_COMPOSE")
  EXTRA_VARS+=(-e "@$DCS_VARS")
  PROJECT_NAME="${PROJECT_NAME}-${DCS}"
fi

cleanup() {
  if [ "$KEEP" = false ]; then
    echo "==> Tearing down containers..."
    docker compose -p "$PROJECT_NAME" "${COMPOSE_ARGS[@]}" down -v --remove-orphans 2>/dev/null || true
  else
    echo "==> Keeping containers running (use 'docker compose -p $PROJECT_NAME ${COMPOSE_ARGS[*]} down -v' to clean up)"
  fi
}

trap cleanup EXIT

# Step 0: Offline template checks. No containers involved, so run them first:
# they are the only tests that can observe a topology this harness does not
# deploy, in particular a cluster with nothing in the 'pgbouncer' group.
echo "==> Step 0: Checking rendered templates..."
python3 "$SCRIPT_DIR/render/check-haproxy.py"

# Step 1: Generate SSH keypair and copy to Docker build context
echo "==> Step 1: Ensuring SSH keypair exists..."
mkdir -p "$SCRIPT_DIR/.ssh"
if [ ! -f "$SCRIPT_DIR/.ssh/id_ed25519" ]; then
  ssh-keygen -t ed25519 -f "$SCRIPT_DIR/.ssh/id_ed25519" -N "" -q
  echo "    Generated new SSH keypair"
else
  echo "    Using existing SSH keypair"
fi
cp "$SCRIPT_DIR/.ssh/id_ed25519.pub" "$SCRIPT_DIR/docker/authorized_keys"

# Step 2: Build containers
echo "==> Step 2: Building Docker images..."
docker compose -p "$PROJECT_NAME" "${COMPOSE_ARGS[@]}" build

# Step 3: Start containers
echo "==> Step 3: Starting containers..."
docker compose -p "$PROJECT_NAME" "${COMPOSE_ARGS[@]}" up -d

# Step 4: Wait for SSH
echo "==> Step 4: Waiting for SSH on all containers..."
# Extract IPs from inventory
HOSTS=$(grep -oP '192\.168\.6\.\d+' "$INVENTORY" | sort -u)
MAX_WAIT=60

for host in $HOSTS; do
  ELAPSED=0
  while ! ssh -i "$SCRIPT_DIR/.ssh/id_ed25519" \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=2 \
    -o BatchMode=yes \
    ansible@"$host" true 2>/dev/null; do
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
      echo "ERROR: Timed out waiting for SSH on $host"
      exit 1
    fi
    sleep 2
  done
  echo "    SSH ready on $host"
done

# Step 4b: Wait for the external DCS to elect a leader
if [ "$DCS" = "consul" ]; then
  echo "==> Step 4b: Waiting for Consul to elect a leader..."
  ELAPSED=0
  until [ -n "$(curl -sf http://192.168.6.20:8500/v1/status/leader |
                tr -d '"')" ]; do
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge 60 ]; then
      echo "ERROR: Consul did not elect a leader within 60s"
      exit 1
    fi
    sleep 2
  done
  echo "    Consul leader elected"
fi

# Step 5: Build and install Ansible collection
echo "==> Step 5: Building and installing Ansible collection..."
cd "$PROJECT_DIR"
make install

# Step 6: Install Galaxy dependencies
echo "==> Step 6: Installing Galaxy dependencies..."
ansible-galaxy collection install -r "$PROJECT_DIR/galaxy.template.yml" --force 2>/dev/null || \
  echo "    Warning: Some Galaxy dependencies may not have installed"

# Step 7: Run the sample playbook
echo "==> Step 7: Running playbook: $PLAYBOOK"
ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$PLAYBOOK" \
  -i "$INVENTORY" \
  --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
  "${EXTRA_VARS[@]}" \
  -v

# Step 7b: A second consecutive run of the pooler roles must change nothing.
echo "==> Step 7b: Checking the pooler roles are idempotent..."
"$SCRIPT_DIR/check-idempotence.sh" \
  "$INVENTORY" \
  "$PLAYBOOK" \
  --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
  "${EXTRA_VARS[@]}"

# Step 8: Run verification
if [ -f "$VERIFY_PLAYBOOK" ]; then
  echo "==> Step 8: Running verification playbook..."
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
    "$VERIFY_PLAYBOOK" \
    -i "$INVENTORY" \
    --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
    "${EXTRA_VARS[@]}" \
    -v
else
  echo "==> Step 8: No verification playbook found, skipping"
fi

echo ""
echo "========================================="
echo "  TEST PASSED: ${SCENARIO} on ${OS}"
echo "========================================="
