#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <scenario> <os> [dcs] [backup] [--keep]"
  echo "  scenario: simple-cluster | ultra-ha | simple-cluster-coldfront"
  echo "  os:       debian12 | rocky9"
  echo "  dcs:      etcd3 (default) | consul"
  echo "  backup:   ssh (default) | s3 -- the repository; s3 is ultra-ha only"
  echo "  --keep:   don't tear down containers after test"
  exit 1
}

SCENARIO="${1:-}"
OS="${2:-}"
DCS="etcd3"
BACKUP="ssh"
KEEP=false

# Everything after the OS is recognised by its value, so the DCS and the backup
# type can each be given without the other.
for arg in "${@:3}"; do
  case "$arg" in
    --keep) KEEP=true ;;
    ssh|s3) BACKUP="$arg" ;;
    *) DCS="$arg" ;;
  esac
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

# The repository. SSH layers the backup servers onto the inventory; S3 adds the
# MinIO container and the variables pointing at it, and has no backup servers,
# which init_server would refuse in an S3 zone. A scenario without an SSH layer
# deploys no backup servers at all, which is the simple cluster's normal case.
SSH_INVENTORY="$SCRIPT_DIR/inventories/${SCENARIO}-ssh.yml"
INVENTORY_ARGS=(-i "$INVENTORY")

case "$BACKUP" in
  ssh)
    if [ -f "$SSH_INVENTORY" ]; then
      INVENTORY_ARGS+=(-i "$SSH_INVENTORY")
    fi
    ;;
  s3)
    if [ "$SCENARIO" != "ultra-ha" ]; then
      echo "ERROR: an S3 repository is only tested with ultra-ha"
      exit 1
    fi
    COMPOSE_ARGS+=(-f "$SCRIPT_DIR/compose/backup-s3.yml")
    EXTRA_VARS+=(-e "@$SCRIPT_DIR/vars/backup-s3.yml")
    PROJECT_NAME="${PROJECT_NAME}-s3"
    ;;
  *)
    echo "ERROR: unknown backup type: $BACKUP"
    usage
    ;;
esac

# A scenario's own extra vars, passed to every playbook run below. The
# ColdFront scenario keeps its object store's address and bucket here,
# and Step 4d reads them from this file to wait for the bucket.
SCENARIO_VARS="$SCRIPT_DIR/vars/${SCENARIO}.yml"
if [ -f "$SCENARIO_VARS" ]; then
  EXTRA_VARS+=(-e "@$SCENARIO_VARS")
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
# deploy, in particular a cluster with pgbouncer_enabled unset.
echo "==> Step 0: Checking rendered templates..."
python3 "$SCRIPT_DIR/render/check-haproxy.py"
python3 "$SCRIPT_DIR/render/check-patroni.py"
python3 "$SCRIPT_DIR/render/check-pgbackrest.py"

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
# Extract IPs from the inventories in use
HOSTS=$(ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" \
  ansible all "${INVENTORY_ARGS[@]}" --list-hosts | tail -n +2)
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

# Step 4c: Wait for the object store and hand its CA to the nodes
if [ "$BACKUP" = "s3" ]; then
  echo "==> Step 4c: Preparing the S3 repository..."
  "$SCRIPT_DIR/prepare-s3.sh" "$PROJECT_NAME" "${COMPOSE_ARGS[@]}" -- \
    "${INVENTORY_ARGS[@]}" --private-key "$SCRIPT_DIR/.ssh/id_ed25519"
fi

# Step 4d: Wait for the scenario's object store bucket
# The compose stack creates the bucket from a side container, which can
# still be running once every host answers SSH. setup_lakekeeper writes
# to the bucket to prove the warehouse credentials work, and fails
# rather than waits if the bucket is not there yet. Each check gives up
# after 2s, so a filer that accepts the connection but never answers
# cannot keep the loop waiting indefinitely.
FILER=""
if [ -f "$SCENARIO_VARS" ]; then
  FILER=$(sed -n 's/^seaweedfs_filer: *//p' "$SCENARIO_VARS")
fi
if [ -n "$FILER" ]; then
  BUCKET=$(sed -n 's/^coldfront_s3_bucket: *//p' "$SCENARIO_VARS")
  echo "==> Step 4d: Waiting for the $BUCKET bucket..."
  ELAPSED=0
  until curl -sf --max-time 2 -o /dev/null "$FILER/buckets/$BUCKET/"; do
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge 60 ]; then
      echo "ERROR: Bucket $BUCKET did not appear within 60s"
      exit 1
    fi
    sleep 2
  done
  echo "    Bucket $BUCKET ready"
fi

# Step 5: Build and install Ansible collection
echo "==> Step 5: Building and installing Ansible collection..."
cd "$PROJECT_DIR"
make clean install

# Step 6: Install Galaxy dependencies
echo "==> Step 6: Installing Galaxy dependencies..."
ansible-galaxy collection install -r "$PROJECT_DIR/galaxy.template.yml" --force 2>/dev/null || \
  echo "    Warning: Some Galaxy dependencies may not have installed"

# Step 7: Run the sample playbook
echo "==> Step 7: Running playbook: $PLAYBOOK"
ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
  "$PLAYBOOK" \
  "${INVENTORY_ARGS[@]}" \
  --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
  "${EXTRA_VARS[@]}" \
  -v

# Step 7b: A second consecutive run of the pooler roles must change nothing.
echo "==> Step 7b: Checking the pooler roles are idempotent..."
"$SCRIPT_DIR/check-idempotence.sh" \
  "$INVENTORY" \
  "$PLAYBOOK" \
  "${INVENTORY_ARGS[@]:2}" \
  --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
  "${EXTRA_VARS[@]}"

# Step 8: Run verification
if [ -f "$VERIFY_PLAYBOOK" ]; then
  echo "==> Step 8: Running verification playbook..."
  ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg" ansible-playbook \
    "$VERIFY_PLAYBOOK" \
    "${INVENTORY_ARGS[@]}" \
    --private-key "$SCRIPT_DIR/.ssh/id_ed25519" \
    "${EXTRA_VARS[@]}" \
    -v
else
  echo "==> Step 8: No verification playbook found, skipping"
fi

echo ""
echo "========================================="
echo "  TEST PASSED: ${SCENARIO} on ${OS} (dcs=${DCS}, backup=${BACKUP})"
echo "========================================="
