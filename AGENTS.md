# AGENTS.md

Guidance for coding agents and AI reviewers working in this repository.

## What this is

`pgedge.platform`: an Ansible collection that deploys and manages pgEdge
Distributed Postgres clusters. Postgres nodes in several **zones** replicate
to each other active-active through the **Spock** extension. A simple cluster
has one node per zone. An Ultra-HA cluster has several nodes per zone, kept
highly available by Patroni with etcd or Consul, with HAProxy in front and an
optional pgBackRest backup server.

The collection is not a set of independent installers. It manages **one
cluster as a whole**, and running the playbook again is how a deployed
cluster is changed: add hosts, zones or databases, or change parameters, then
rerun the same playbook against the whole inventory.

## Rules that reviews keep getting wrong

- **`--limit` is not a supported way to run this collection, ever.** Nor are
  `strategy: free` and `serial`; see "Execution Strategy" in
  `docs/configure_playbook.md`. Nearly every role depends on the full list of
  hosts: a proxy needs every node in its zone, and Spock needs every zone.
  Checks that stop a limited run are safeguards, not support for it. Don't
  report "breaks under `--limit`" as a defect. Don't add code or docs that
  accommodate or advise limiting a run.
- **A run must be idempotent.** A second run against a deployed cluster
  changes nothing and reports nothing changed, even after Patroni has moved a
  zone's leader. The e2e tests enforce this with `tests/check-idempotence.sh`.
- **Writes to a zone go to its current primary,** found by
  `role_config/tasks/zone_primary.yaml`. That is not necessarily the zone's
  first node.

## Layout

- `roles/`: one directory per role. `install_*` roles install packages;
  `setup_*` roles configure and start services. `init_server` prepares hosts,
  `finalize_backrest` takes the first backup, `recover_postgres` restores from
  backup, `remove_zone` detaches a zone, and `wipe_cluster` tears down.
- `roles/role_config`: shared defaults and derived variables (`vars/main.yaml`)
  that every other role depends on through `meta/main.yaml`. It also holds
  shared task files that other roles include, such as `zone_primary`,
  `sizing_floor` and `pgpass_entry`.
- `roles/setup_pgedge`: Spock nodes, subscriptions and replication sets.
  `classify.yaml` reads every zone's Spock state before anything is created.
  `join_*.yaml` add a zone to a running cluster that holds data, gated by
  `-e pgedge_join_zones=<N>`.
- `sample-playbooks/`: the supported playbooks, one per topology plus
  recovery, zone removal and wipe. Play order matters and is explained in
  their comments.
- `docs/`: the MkDocs site (`mkdocs.yml`). It has one page per role under
  `docs/roles/`, the variable reference under `docs/configuration/`, and
  troubleshooting under `docs/troubleshooting/`.
- `tests/`: end-to-end tests on Docker containers.
  - `compose/`: one file per topology and OS.
  - `inventories/`: base inventories plus layers.
  - `playbooks/`: test-only playbooks.
  - `verify/`: post-deploy checks.
  - `render/`: offline template renders compared against fixtures.
  - `run-test.sh` and `zone-join-scenarios.sh`: drivers.
- `.github/workflows/`: `simple-cluster.yml` and `ultra-ha.yml` run the e2e
  matrix on `workflow_dispatch`. `release.yml` builds the release.

## Key concepts

- A zone number is a host's `zone` variable. It is also the Snowflake node ID
  and names the Spock node `edge<N>`. Subscriptions are named `sub_n<X>_n<Y>`:
  node X subscribes to node Y. Spock subscribes zone to zone, through HAProxy
  on Ultra-HA.
- Inventory groups are `pgedge` (Postgres nodes), `haproxy` and `backup`.
  `db_names` must be the same on every pgEdge node.
- Worker and slot pool sizes are calculated from the cluster. The
  `sizing_floor` task file keeps a later run from shrinking them below what
  the zones were configured with.

## Working conventions

- Task modules use short names (`command`, `assert`), as the existing code
  does, not FQCNs. Comments explain why, in full sentences.
- Every user-visible change gets an entry in `docs/CHANGELOG.md` (brief) and
  in `docs/release_notes/unreleased.md` (full), tagged with its ticket
  (`EE-NN`) or PR (`#NN`). Change the role and configuration docs with the
  code.
- The docs voice is plain declarative sentences with no marketing. Run
  `mkdocs build --strict` after changing docs.
- `make install` builds the collection and installs it into
  `~/.ansible/collections`. Point `ANSIBLE_COLLECTIONS_PATH` at a link to the
  working tree to test without installing.
- The e2e tests run locally with `act` on the two workflows, or with
  `tests/run-test.sh <scenario> <os>`. They use compose project `e2e` with
  fixed addresses on 192.168.6.0/24, so only one test cluster runs on a host
  at a time.
- Never put customer names or other identifying data in code, tests, issues
  or PRs.
