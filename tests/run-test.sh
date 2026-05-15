#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <scenario> <os> [--keep]"
  echo "  scenario: simple-cluster | ultra-ha"
  echo "  os:       debian12 | rocky9"
  echo "  --keep:   don't tear down containers after test"
  exit 1
}

SCENARIO="${1:-}"
OS="${2:-}"
KEEP=false

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

cleanup() {
  if [ "$KEEP" = false ]; then
    echo "==> Tearing down containers..."
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
  else
    echo "==> Keeping containers running (use 'docker compose -p $PROJECT_NAME -f $COMPOSE_FILE down -v' to clean up)"
  fi
}

trap cleanup EXIT

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
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build

# Step 3: Start containers
echo "==> Step 3: Starting containers..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d

# Step 4: Wait for SSH
echo "==> Step 4: Waiting for SSH on all containers..."
# Extract IPs from inventory
HOSTS=$(grep -oP '192\.168\.6\.\d+' "$INVENTORY" | sort -u)
MAX_WAIT=60
ELAPSED=0

for host in $HOSTS; do
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
  -v

# Step 8: Run verification
if [ -f "$VERIFY_PLAYBOOK" ]; then
  echo "==> Step 8: Running verification playbook..."
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
    "$VERIFY_PLAYBOOK" \
    -i "$INVENTORY" \
    --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
    -v
else
  echo "==> Step 8: No verification playbook found, skipping"
fi

echo ""
echo "========================================="
echo "  TEST PASSED: ${SCENARIO} on ${OS}"
echo "========================================="
