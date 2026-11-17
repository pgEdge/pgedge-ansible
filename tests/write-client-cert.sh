#!/bin/bash
# Write the pgEdge repository client certificate and key, given in the
# PGEDGE_REPO_CLIENT_CRT and PGEDGE_REPO_CLIENT_KEY environment variables, to
# tests/.certs/client.crt and client.key, where the workflows' CERT_ARGS point
# pgedge_client_cert_src and pgedge_client_key_src.
#
#   PGEDGE_REPO_CLIENT_CRT=... PGEDGE_REPO_CLIENT_KEY=... tests/write-client-cert.sh
#
# The workflows set the two variables from secrets of the same names. The
# certificate is passed to the playbooks as a path rather than inline so no key
# material reaches the process arguments. tests/.certs is ignored by git.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$SCRIPT_DIR/.certs"

# An empty secret would write a lone newline, which `test -s` accepts, so the
# deployment would get invalid credentials instead of failing here. Check the
# values before they reach a file.
: "${PGEDGE_REPO_CLIENT_CRT:?is empty or unset}"
: "${PGEDGE_REPO_CLIENT_KEY:?is empty or unset}"

# The key is never readable by anyone else, not even between its creation and
# the write.
install -d -m 0700 "$CERT_DIR"
install -m 0600 /dev/null "$CERT_DIR/client.key"
printf '%s\n' "$PGEDGE_REPO_CLIENT_CRT" > "$CERT_DIR/client.crt"
printf '%s\n' "$PGEDGE_REPO_CLIENT_KEY" > "$CERT_DIR/client.key"
