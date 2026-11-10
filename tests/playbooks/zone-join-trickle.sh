#!/bin/bash
# Write a trickle of rows into one zone of a cluster, through that zone's
# normal endpoint, for as long as a zone join test needs writes in flight.
# tests/playbooks/zone-join-trickle.yml installs this on the client and runs
# one copy per zone and database, each as its own systemd unit.
#
#   zone-join-trickle.sh <zone> <database> <host> <port> <user> <state dir>
#
# Each row is (zone, seq, ts) in zone_join_trickle, where seq counts up from 1
# for the zone and is never skipped. A row counts once Postgres acknowledges
# its commit, and the last one acknowledged is written to
# <state dir>/<database>-zone<zone>.last. So the zone holds exactly the rows 1
# to that number, and after a join every other zone has to hold the same:
# verify-zone-join.yml compares them.
#
# The writer has to outlive anything a join test does to the zone: a restart,
# a switchover, a proxy that drops the connection. A failed insert is logged
# and tried again with the same seq, about once a second, until it goes
# through. The commit may have landed even though psql reported a failure,
# when the connection went after the commit and before the answer, so the
# retry does nothing if the row is already there and is acknowledged all the
# same.
#
# SIGTERM stops it between inserts, never during one: the insert in flight is
# finished and recorded first. The unit runs with KillMode=mixed, so psql
# itself is not signalled.
#
# The password comes from PGPASSFILE, which the unit sets.

set -u

if [ $# -ne 6 ]; then
  echo "Usage: $0 <zone> <database> <host> <port> <user> <state dir>" >&2
  exit 2
fi

ZONE="$1"
DB="$2"
HOST="$3"
PORT="$4"
USER_NAME="$5"
STATE_DIR="$6"
INTERVAL="${ZONE_JOIN_TRICKLE_INTERVAL:-1}"

LAST_FILE="$STATE_DIR/$DB-zone$ZONE.last"
LOG_FILE="$STATE_DIR/$DB-zone$ZONE.log"

# A statement that hangs, on a proxy that has lost its server or a primary
# that is going down, is abandoned and retried rather than left to stall the
# writer.
export PGOPTIONS="-c statement_timeout=10s"
CONN="host=$HOST port=$PORT dbname=$DB user=$USER_NAME connect_timeout=5 application_name=zone_join_trickle"

STOPPING=false
trap 'STOPPING=true' TERM INT

log() {
  printf '%s zone %s %s: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" \
    "$ZONE" "$DB" "$*" >>"$LOG_FILE"
}

# Sleep in the background and wait for it, so that SIGTERM ends the wait at
# once instead of after the sleep.
pause() {
  sleep "$INTERVAL" &
  wait $! 2>/dev/null
}

record() {
  printf '%s\n' "$1" >"$LAST_FILE.tmp" && mv -f "$LAST_FILE.tmp" "$LAST_FILE"
}

# Carry on from the last row recorded, or from the last the zone holds if
# that is further: a writer killed outright, rather than stopped, can have
# committed a row it never recorded. Either way seq stays unbroken.
LAST=0
if [ -s "$LAST_FILE" ]; then
  LAST=$(cat "$LAST_FILE")
fi

HELD=""
until [ -n "$HELD" ] || $STOPPING; do
  if ! HELD=$(psql "$CONN" -X -A -t -q -v ON_ERROR_STOP=1 -c \
      "SELECT coalesce(max(seq), 0) FROM zone_join_trickle
        WHERE origin_zone = $ZONE" 2>>"$LOG_FILE"); then
    HELD=""
    log "cannot read the zone's last row from $HOST:$PORT; retrying"
    pause
  fi
done

if [ -n "$HELD" ] && [ "$HELD" -gt "$LAST" ]; then
  log "the zone holds rows up to $HELD, past the $LAST recorded; carrying on from there"
  LAST="$HELD"
fi
record "$LAST"
log "started at seq $((LAST + 1)) through $HOST:$PORT"

FAILING=false
while ! $STOPPING; do
  SEQ=$((LAST + 1))
  if psql "$CONN" -X -q -v ON_ERROR_STOP=1 -c \
      "INSERT INTO zone_join_trickle (origin_zone, seq, ts)
       VALUES ($ZONE, $SEQ, clock_timestamp())
       ON CONFLICT (origin_zone, seq) DO NOTHING" 2>>"$LOG_FILE"; then
    LAST="$SEQ"
    record "$LAST"
    if $FAILING; then
      log "seq $SEQ went through; writing again"
      FAILING=false
    fi
  else
    log "seq $SEQ failed; retrying"
    FAILING=true
  fi
  if ! $STOPPING; then
    pause
  fi
done

log "stopped; the last row written is seq $LAST"
