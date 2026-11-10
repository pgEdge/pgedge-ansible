#!/bin/bash
# Run one zone-join test scenario against the test containers. The workflows
# call this once per scenario, in order, against one set of containers, each
# scenario starting from the cluster the one before it left:
#
#   tests/zone-join-scenarios.sh <topology> <scenario> [ansible-playbook args...]
#
#   topology  simple-cluster | ultra-ha
#   args      everything the deployment needs beyond the base inventory and
#             the zone-join layers, which this adds itself: the repository's
#             inventory layer, --private-key, -e repo_environment=..., the
#             DCS's variables and so on. Passed to every playbook run here.
#
# Every run uses tests/inventories/<topology>.yml with zone-join.yml layered
# on; once the new zones are in play, simple-zone-join.yml or
# ultra-ha-zone-join.yml as well.
#
# Scenarios, in the order the workflows run them:
#
#   deploy        A first deployment with -e pgedge_join_zones refuses, since
#                 there is no running cluster to join; without it, the cluster
#                 is built. Then the seed data, a check that the cluster
#                 verifies before any zone joins, and the trickle is started.
#   gate          (simple-cluster) With the new zones in the inventory, a run
#                 without the flag refuses before creating anything for them,
#                 and so does a run with the flag that also adds a database.
#   join-two      (simple-cluster) Zones 4 and 5 join in one run, stopped
#                 while zone 5 copies; the same command again skips zone 4 and
#                 finishes zone 5. Verified, then a second run with and
#                 without the flag changes nothing.
#   resume-step4  (simple-cluster) Zone 5 removed, and joined again with its
#                 source's apply held back, so the join fails after step 3 and
#                 says what it holds; the same command then finishes it.
#   not-resumable (simple-cluster) As resume-step4, but a table is created on
#                 zone 5 before the rerun: the rerun refuses and releases the
#                 slots on the other zones. remove_zone resets it.
#   copy-died     (simple-cluster) Zone 5's join stopped during the copy's data
#                 step and its Postgres restarted: the rerun finds the copy
#                 cannot go on, releases the slots, and remove_zone resets it.
#   autoddl       (simple-cluster) Zone 5 joins while the members create
#                 tables and write to them, and they create and write more
#                 after; every zone, zone 5 included, ends with all of it.
#                 Verified, and second runs change nothing.
#   remove-unreachable
#                 (simple-cluster) Zone 5's container stopped: remove_zone
#                 cleans the other zones, and a second run changes nothing.
#   join-ha       (ultra-ha) Zone 3 joins under the trickle. Verified,
#                 including its replica; then a second run with and without
#                 the flag, and one after a switchover in every zone, change
#                 nothing.
#
# Interruptions use test playbooks and signals, never a role variable:
# tests/playbooks/zone-join-wait.yml finds the moment, and the deployment
# running in the background is stopped there; tests/playbooks/zone-join-hold.yml
# holds the source's apply back so step 4 cannot finish.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

TOPOLOGY="${1:-}"
SCENARIO="${2:-}"
if [ -z "$TOPOLOGY" ] || [ -z "$SCENARIO" ]; then
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi
shift 2
ARGS=("$@")

case "$TOPOLOGY" in
  simple-cluster)
    NEW_ZONES=(4 5)
    JOIN_LAYER="$SCRIPT_DIR/inventories/simple-zone-join.yml"
    ;;
  ultra-ha)
    NEW_ZONES=(3)
    JOIN_LAYER="$SCRIPT_DIR/inventories/ultra-ha-zone-join.yml"
    ;;
  *)
    echo "ERROR: unknown topology: $TOPOLOGY" >&2
    exit 1
    ;;
esac

export ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg"
BASE_INVENTORY="$SCRIPT_DIR/inventories/$TOPOLOGY.yml"
PLAYBOOK="$SCRIPT_DIR/playbooks/$TOPOLOGY.yml"
REMOVE_PLAYBOOK="$PROJECT_DIR/sample-playbooks/remove-zone/playbook.yaml"
# Without and with the new zones' hosts.
BEFORE=(-i "$BASE_INVENTORY" "${ARGS[@]}" -i "$SCRIPT_DIR/inventories/zone-join.yml")
WITH=("${BEFORE[@]}" -i "$JOIN_LAYER")
# Ansible only warns about an inventory it cannot find, and would run on
# without the new zones.
for f in "$BASE_INVENTORY" "$SCRIPT_DIR/inventories/zone-join.yml" "$JOIN_LAYER"; do
  [ -f "$f" ] || { echo "ERROR: inventory not found: $f" >&2; exit 1; }
done
LOG_DIR="${ZONE_JOIN_LOG_DIR:-$(mktemp -d)}"
mkdir -p "$LOG_DIR"

step() {
  echo ""
  echo "==> $*"
}

play() {
  ansible-playbook "$@"
}

# The deployment playbook, with the new zones in the inventory.
deploy() {
  play "$PLAYBOOK" "${WITH[@]}" "$@"
}

# Run the deployment and require it to fail with a message containing each
# pattern given before --. The output is kept in $LOG_DIR/<name>.log.
expect_failure() {
  local name="$1"
  shift
  local patterns=()
  while [ "$1" != -- ]; do
    patterns+=("$1")
    shift
  done
  shift
  local log="$LOG_DIR/$name.log"
  if "$@" >"$log" 2>&1; then
    cat "$log"
    echo "ERROR: $name: the run succeeded, and should have failed." >&2
    exit 1
  fi
  # Ansible folds long messages across lines in its output; compare on one.
  local flat
  flat=$(tr -s ' \n' ' ' <"$log")
  for pattern in "${patterns[@]}"; do
    if ! grep -qF -- "$pattern" <<<"$flat"; then
      cat "$log"
      echo "ERROR: $name: the run failed, but without \"$pattern\"." >&2
      exit 1
    fi
  done
  grep -E 'fatal:|FAILED!|msg' "$log" | tail -n 5 || true
  echo "    $name: failed as expected."
}

join_flag() {
  local IFS=,
  echo "{\"pgedge_join_zones\": [$*]}"
}

trickle() {
  play "$SCRIPT_DIR/playbooks/zone-join-trickle.yml" "${WITH[@]}" \
    -e zone_join_trickle="$1" "${@:2}"
}

verify() {
  trickle stop
  play "$SCRIPT_DIR/verify/verify-zone-join.yml" "${WITH[@]}"
}

idempotent() {
  "$SCRIPT_DIR/check-idempotence.sh" "$BASE_INVENTORY" "$PLAYBOOK" \
    "${WITH[@]:2}" "$@"
}

remove_zone() {
  play "$REMOVE_PLAYBOOK" "${WITH[@]}" -e remove_zone="$1" \
    -e remove_zone_confirm=true
}

removed() {
  play "$SCRIPT_DIR/playbooks/remove-zone-verify.yml" "${WITH[@]}" \
    -e remove_zone="$1" "${@:2}"
}

hold() {
  play "$SCRIPT_DIR/playbooks/zone-join-hold.yml" "${WITH[@]}" \
    -e zone_join_hold="$1"
}

# A deployment in the background, in a process group of its own so that
# stopping it stops every worker it forked, as an operator's Ctrl-C would.
DEPLOY_PID=""
deploy_in_background() {
  local log="$LOG_DIR/$1.log"
  shift
  setsid ansible-playbook "$PLAYBOOK" "${WITH[@]}" "$@" >"$log" 2>&1 &
  DEPLOY_PID=$!
  echo "    deployment running in the background ($DEPLOY_PID), logging to $log"
}

stop_deploy() {
  if kill -0 "$DEPLOY_PID" 2>/dev/null; then
    kill -INT -- "-$DEPLOY_PID" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$DEPLOY_PID" 2>/dev/null || break
      sleep 1
    done
    kill -KILL -- "-$DEPLOY_PID" 2>/dev/null || true
  fi
  wait "$DEPLOY_PID" 2>/dev/null || true
  DEPLOY_PID=""
}

finish_deploy() {
  local log="$1"
  if ! wait "$DEPLOY_PID"; then
    cat "$log"
    echo "ERROR: the deployment in the background failed." >&2
    exit 1
  fi
  DEPLOY_PID=""
  tail -n 20 "$log"
}

cleanup() {
  if [ -n "$DEPLOY_PID" ]; then
    stop_deploy
  fi
}
trap cleanup EXIT

wait_for_copy() {
  play "$SCRIPT_DIR/playbooks/zone-join-wait.yml" "${WITH[@]}" \
    -e zone_join_wait_zone="$1" -e zone_join_wait_for="$2"
}

# Run SQL as postgres on a host of the inventory, by address.
psql_on() {
  local host="$1" db="$2" sql="$3"
  ssh -i "$SCRIPT_DIR/.ssh/id_ed25519" -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o LogLevel=ERROR \
    ansible@"$host" \
    "cd /tmp && sudo -u postgres psql -X -d $db -v ON_ERROR_STOP=1 -t -A -c \"$sql\""
}

on_host() {
  local host="$1"
  shift
  ssh -i "$SCRIPT_DIR/.ssh/id_ed25519" -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o LogLevel=ERROR \
    ansible@"$host" "$@"
}

# The address of zone N's only node, in the simple cluster.
simple_host() {
  echo "192.168.6.$((9 + $1))"
}

case "$SCENARIO" in
deploy)
  step "A first deployment with pgedge_join_zones refuses: there is nothing to join"
  expect_failure deploy-with-flag \
    "no database in db_names holds data on any zone with a Spock node" \
    "run this again without pgedge_join_zones" -- \
    play "$PLAYBOOK" "${BEFORE[@]}" -e "$(join_flag 1)"

  step "Deploy the cluster without the new zones"
  play "$PLAYBOOK" "${BEFORE[@]}"

  step "Seed it, and check it verifies before any zone joins"
  play "$SCRIPT_DIR/playbooks/zone-join-seed.yml" "${BEFORE[@]}"
  play "$SCRIPT_DIR/playbooks/zone-join-trickle.yml" "${BEFORE[@]}" \
    -e zone_join_trickle=start
  play "$SCRIPT_DIR/playbooks/zone-join-trickle.yml" "${BEFORE[@]}" \
    -e zone_join_trickle=stop
  play "$SCRIPT_DIR/verify/verify-zone-join.yml" "${BEFORE[@]}"

  step "Start the trickle for the joins"
  trickle start
  ;;

gate)
  step "With zones ${NEW_ZONES[*]} in the inventory, a run without pgedge_join_zones refuses"
  expect_failure gate-no-flag \
    "are not yet part of this cluster, which already holds data" \
    "nothing has been created in Spock" \
    "run this again with -e pgedge_join_zones=$(IFS=,; echo "${NEW_ZONES[*]}")" -- \
    deploy
  for z in "${NEW_ZONES[@]}"; do
    step "Nothing refers to zone $z, and zone $z has nothing"
    removed "$z"
  done

  step "A run that joins zones and adds a database refuses (one change per run)"
  expect_failure gate-db-added \
    "zj_added is in db_names but not yet in Spock on any zone" \
    "Adding a database and joining a zone are separate changes" -- \
    deploy -e "$(join_flag "${NEW_ZONES[@]}")" \
    -e '{"db_names": ["demo", "zonejoin", "zj_added"]}'
  for z in "${NEW_ZONES[@]}"; do
    removed "$z"
  done
  ;;

join-two)
  step "Join zones 4 and 5, and stop the run while zone 5 copies"
  deploy_in_background join-two-first -e "$(join_flag 4 5)"
  wait_for_copy 5 copying
  stop_deploy
  if ! grep -q "Report that zone 4 has joined" "$LOG_DIR/join-two-first.log"; then
    tail -n 40 "$LOG_DIR/join-two-first.log"
    echo "ERROR: zone 4 had not finished joining when zone 5 was caught copying." >&2
    exit 1
  fi

  step "The same command again: zone 4 is skipped, zone 5 carries on"
  deploy -e "$(join_flag 4 5)" | tee "$LOG_DIR/join-two-again.log"
  tr -s ' \n' ' ' <"$LOG_DIR/join-two-again.log" |
    grep -qF "Zone 4 in pgedge_join_zones is already a member of every database that holds data, and is skipped" || {
      echo "ERROR: the rerun did not skip zone 4 as a member." >&2
      exit 1
    }

  step "Verify all five zones"
  verify

  step "A second run changes nothing, with the flag and without it"
  idempotent -e "$(join_flag 4 5)"
  idempotent

  # Zone 4 is a member now, so it takes writes for the joins to come.
  trickle start -e zone_join_trickle_zones=1,2,3,4
  ;;

resume-step4)
  step "Remove zone 5"
  remove_zone 5
  removed 5

  step "Join zone 5 with its source's apply held: the join stops in step 4"
  hold start
  expect_failure resume-step4-held \
    "Zone 5 did not finish joining demo" \
    "This can be resumed: run the same command again" \
    "on zone 2 (192.168.6.11), holding" \
    "on zone 3 (192.168.6.12), holding" \
    "on zone 4 (192.168.6.13), holding" \
    "pg_drop_replication_slot" -- \
    deploy -e "$(join_flag 5)" -e pgedge_join_wait_minutes=1
  hold stop

  step "The same command again finishes the join"
  deploy -e "$(join_flag 5)"
  verify
  trickle start -e zone_join_trickle_zones=1,2,3,4
  ;;

not-resumable)
  step "Remove zone 5, and stop its join again after step 3"
  remove_zone 5
  removed 5
  hold start
  expect_failure not-resumable-held \
    "This can be resumed" -- \
    deploy -e "$(join_flag 5)" -e pgedge_join_wait_minutes=1
  hold stop

  step "Write to zone 5 before the rerun: the join can no longer be resumed"
  psql_on "$(simple_host 5)" demo "CREATE TABLE zj_stray (id int PRIMARY KEY)"
  expect_failure not-resumable-rerun \
    "Zone 5 cannot join demo: it holds tables the join did not copy" \
    "Every other zone has dropped the subscriptions, replication slots and node" \
    "-e remove_zone=5 -e remove_zone_confirm=true" -- \
    deploy -e "$(join_flag 5)"

  step "The other zones no longer hold anything for zone 5"
  removed 5 -e remove_zone_verify_removed=false

  step "remove_zone resets zone 5"
  remove_zone 5
  removed 5
  ;;

copy-died)
  step "Join zone 5, and stop the run while its copy is in the data step"
  deploy_in_background copy-died-first -e "$(join_flag 5)"
  wait_for_copy 5 data
  stop_deploy

  step "Restart zone 5's Postgres mid-copy"
  on_host "$(simple_host 5)" \
    'sudo systemctl restart $(systemctl list-units --plain --no-legend --state=active "postgresql@*" "pgedge-postgres-*" | awk "{print \$1}")'

  step "The rerun finds the copy cannot go on, and releases the other zones"
  expect_failure copy-died-rerun \
    "Zone 5 cannot finish joining demo, and the join cannot be resumed" \
    "stopped where Spock cannot continue it" \
    "-e remove_zone=5 -e remove_zone_confirm=true" -- \
    deploy -e "$(join_flag 5)"
  removed 5 -e remove_zone_verify_removed=false

  step "remove_zone resets zone 5"
  remove_zone 5
  removed 5
  ;;

autoddl)
  step "Join zone 5, creating tables on every member while it copies"
  deploy_in_background autoddl-join -e "$(join_flag 5)"
  wait_for_copy 5 copying
  play "$SCRIPT_DIR/playbooks/zone-join-autoddl.yml" "${WITH[@]}" \
    -e zone_join_autoddl=during -e zone_join_autoddl_zone=5
  finish_deploy "$LOG_DIR/autoddl-join.log"

  step "Create a table after the join, and write from zone 5 into every one"
  play "$SCRIPT_DIR/playbooks/zone-join-autoddl.yml" "${WITH[@]}" \
    -e zone_join_autoddl=after -e zone_join_autoddl_zone=5
  play "$SCRIPT_DIR/playbooks/zone-join-autoddl.yml" "${WITH[@]}" \
    -e zone_join_autoddl=check -e zone_join_autoddl_zone=5

  step "Verify all five zones, and that second runs change nothing"
  verify
  idempotent -e "$(join_flag 5)"
  idempotent
  ;;

remove-unreachable)
  container=$(docker ps -q --filter label=com.docker.compose.project=e2e |
    xargs -r docker inspect \
    -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' |
    awk -v ip="$(simple_host 5)" '{for (i = 2; i <= NF; i++) if ($i == ip) print substr($1, 2)}')
  if [ -z "$container" ]; then
    echo "ERROR: no running container has $(simple_host 5)." >&2
    exit 1
  fi

  step "Stop zone 5's container ($container), and remove the zone"
  docker stop "$container"
  remove_zone 5
  removed 5

  step "A second removal changes nothing"
  "$SCRIPT_DIR/check-idempotence.sh" "$BASE_INVENTORY" "$REMOVE_PLAYBOOK" \
    "${WITH[@]:2}" -e remove_zone=5 -e remove_zone_confirm=true
  docker start "$container"
  ;;

join-ha)
  step "Join zone 3 under the trickle"
  deploy -e "$(join_flag 3)"

  step "Verify all three zones, zone 3's replica included"
  verify

  step "A second run changes nothing, with the flag and without it"
  idempotent -e "$(join_flag 3)"
  idempotent

  step "Nor does one after a switchover in every zone, zone 3 included"
  play "$SCRIPT_DIR/playbooks/move-leaders.yml" "${WITH[@]}" -e leaders_to=second
  idempotent
  play "$SCRIPT_DIR/playbooks/move-leaders.yml" "${WITH[@]}" -e leaders_to=first
  ;;

*)
  echo "ERROR: unknown scenario: $SCENARIO" >&2
  exit 1
  ;;
esac

echo ""
echo "    Scenario $SCENARIO passed on $TOPOLOGY."
