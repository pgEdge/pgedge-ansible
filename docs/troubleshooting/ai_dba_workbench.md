# AI DBA Workbench Issues

This page covers the pgEdge AI DBA Workbench host that
`install_ai_dba_workbench` and `setup_ai_dba_workbench` build, and the
Workbench's access to the pgEdge nodes. See [AI DBA Workbench
Configuration](../configuration/ai_dba_workbench.md) for the parameters
referenced here, and
[setup_ai_dba_workbench](../roles/setup_ai_dba_workbench.md) for the order the
role does its work in.

## Administrator Refused

**Symptom:** `setup_ai_dba_workbench` fails at "Report why the Workbench
refused its administrator" with HTTP 401, or the web client refuses the
administrator, `ai_dba_workbench_admin_user`.

**Solution:** A run whose first sign-in is refused, as happens after
`ai_dba_workbench_admin_password` changes, sets the inventory's password with
the Workbench's command-line tool and signs in again, so this failure means the
second sign-in was refused as well. The Workbench disables an account after ten
refused sign-ins in a row. Enable it again on the Workbench host, substituting
`ai_dba_workbench_admin_user`, `admin` by default, then run the playbook again:

```bash
sudo -u pgedge /usr/bin/ai-dba-server \
  -config /etc/pgedge/ai-dba-server.yaml \
  -data-dir /var/lib/pgedge/ai-dba-server \
  -enable-user -username <admin-user>
```

HTTP 429 instead means the Workbench's limit on sign-in attempts from one
address. Wait a few minutes and run the playbook again.

## Administrator Password Refused

**Symptom:** `setup_ai_dba_workbench` fails at "Add the administrator to the
Workbench" with `password is too common`.

**Solution:** The Workbench refuses a password on its list of common passwords,
which `init_server` does not check. Set `ai_dba_workbench_admin_password` to
another password, at least 12 characters and at most 72 bytes long, and run the
playbook again.

## The Workbench Does Not Reach a Node

**Symptom:** The Workbench's web client shows a node with a connection error,
or the collector's log reports `no pg_hba.conf entry` or
`password authentication failed` for `ai_dba_workbench_monitor`.

**Solution:** `setup_ai_dba_workbench_monitor` creates the role on the nodes,
and the Workbench's sample playbooks run it after `setup_pgedge`; a playbook
without it leaves the nodes without the role. `setup_postgres`, and
`setup_patroni` on an HA cluster, admit the Workbench host only where the
inventory has an `ai_dba_workbench` host, with the rule `role_config` holds in
`pg_ai_dba_workbench_hba_rules`. A later run against the pgEdge nodes with an
inventory that lacks the `ai_dba_workbench` group removes the rule. Run the
playbook with the complete inventory. A node that was already running when the
run wrote the rule reads it only once it is reloaded, as the
[AI DBA Workbench Configuration](../configuration/ai_dba_workbench.md) page
describes.

`setup_ai_dba_workbench` gives the Workbench each node's
`ai_dba_workbench_monitor_password`, read from that node's variables, and gives
it again to every registered node on the first run after the password changes,
so a run that completed leaves the two in agreement. A password changed on a
node outside the playbook reaches the Workbench only through its web client.

To check a node from the Workbench host, connect as the Workbench does,
substituting the node's address, port, a database and the password:

```bash
PGPASSWORD='<password>' psql \
  "host=<node> port=5432 dbname=demo user=ai_dba_workbench_monitor sslmode=require" \
  -c 'SELECT 1'
```

## Browser Warns About the Certificate

**Symptom:** The browser warns that the connection to
`https://<workbench-host>:8444` is not private.

**Solution:** Unless `ai_dba_workbench_tls_cert_source` and
`ai_dba_workbench_tls_key_source` name a certificate, `setup_ai_dba_workbench`
generates a self-signed one on the controller, in `tls/ai-dba-workbench` beside
the playbook, and a browser warns about a certificate that no authority it
trusts has signed. Accept the warning, have the browser trust
`tls/ai-dba-workbench/server.crt`, or set both parameters to a certificate and
key issued for the host's name and run the playbook again.

## A Workbench Service Fails

**Symptom:** `setup_ai_dba_workbench` stops while waiting for the collector to
build the datastore's schema or for the server to report itself healthy, or one
of the Workbench's services is not running.

**Solution:** The Workbench's services write their output to their own log
files rather than to the journal, one directory each under `/var/log/pgedge`.
All three connect to the datastore's Postgres instance, which runs as the
`ai-dba-workbench-postgres` service:

```bash
sudo systemctl status ai-dba-workbench-postgres pgedge-ai-dba-collector \
  pgedge-ai-dba-server pgedge-ai-dba-alerter nginx
sudo tail -n 100 /var/log/pgedge/ai-dba-*/*.log
```

The server exits at startup when the datastore's schema is missing, which the
collector creates when it starts, and when a key file its configuration names
cannot be read.
