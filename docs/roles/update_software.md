# update_software

The `update_software` role applies minor updates to a deployed cluster's
software. It updates the packages the collection installed to the newest
versions the configured repositories offer, and etcd to the release the
collection installs. It restarts each service that needs it, one host at a
time, in an order that never restarts a zone's primary in place.

This is not what pgEdge calls a rolling upgrade, which replaces nodes with new
ones running a later major release of Postgres or Spock. This role changes no
major version and replaces no node.

The role performs the following tasks when `permit_software_updates` is
`true`:

- Refuse to start when `pg_allow_restart` is `false` on any pgEdge node.
- Refuse to start when any host of the `pgedge`, `haproxy` or `backup` group
  dropped out of the play, unreachable or failed earlier in the playbook.
- Find what each host needs, and report the updates and the order before any
  service is stopped.
- Update the pgEdge nodes one at a time, zone by zone. In each zone the
  replicas go first. Then the leader is switched over to an updated replica
  and updated as a replica.
- Update the Spock and Snowflake extensions in every database, on every
  zone's primary, where the updated packages ship a newer version.
- Update and restart the HAProxy hosts, one at a time.
- Update pgBackRest on every pgEdge node and backup server at once.

When `permit_software_updates` is `false`, which is the default, the role
does nothing.

The role leaves the following alone:

- Packages the collection did not install. Operating system updates are
  yours to apply, but see the note below on what applying them leads to.
- Major versions. The repositories decide what the newest version of a
  package is, and pgEdge's repositories publish a major release of Postgres
  under new package names.
- The Lakekeeper host of a ColdFront cluster.

## Role Dependencies

This role requires the following role for normal operation:

- `role_config` provides shared configuration variables to the role.

## When to Use

The role belongs in the deployment playbook, after every other play, in a
play of its own for the `pgedge`, `haproxy` and `backup` groups. The sample
playbooks already include it:

```yaml
- hosts: pgedge:haproxy:backup
  any_errors_fatal: true
  collections:
    - pgedge.platform
  roles:
    - update_software
```

On a simple cluster, the play needs only the `pgedge` group.

The role stays inert in ordinary runs. To update the cluster, run the
deployment playbook with the gate set on the command line:

```bash
ansible-playbook playbook.yaml -i inventory.yaml \
  -e permit_software_updates=true
```

Don't set `permit_software_updates` in an inventory. Every run of the
playbook would then update whatever the repositories had published since the
last one.

An update restarts Postgres on every pgEdge node that has something to
update. The role refuses to run when `pg_allow_restart` is `false`, rather
than skip the update and leave the impression that it was done:

```
permit_software_updates asks for the cluster's software to be updated,
which restarts Postgres on every pgEdge node, but pg_allow_restart is off
on 192.168.6.10. Allow restarts, or run without permit_software_updates.
```

The role also refuses to start when a host of the cluster dropped out of the
play before it, because it was unreachable or a task failed on it earlier in
the playbook. The update covers every host or none: a backup server left on
the old pgBackRest would refuse every node that took the new one.

To update etcd, change [`etcd_version`](../configuration/etcd.md#etcd_version)
in the inventory to the new release, and run with the gate as above. A later
patch release of the same minor release may also be taken back to an earlier
one this way. An earlier minor release may not: etcd does not start on data a
later minor release has written, and the role refuses such an `etcd_version`
before it changes anything. Nor may `etcd_version` be more than one minor
release past what a node runs, because etcd is upgraded one minor release at a
time. To go from 3.4 to 3.6, set `etcd_version` to a 3.5 release, run with the
gate, then set it to the 3.6 release and run again.

On a simple cluster each zone is a single node, and the zone is unavailable
while its node restarts. On an Ultra-HA cluster each zone has a primary
throughout, except for the few seconds each switchover takes.

## Configuration

This role uses the following parameters:

| Parameter | Use Case |
|-----------|----------|
| `permit_software_updates` | Must be `true` for the role to do anything (default: `false`). Pass it with `-e`. |
| `pg_allow_restart` | Must be `true` on every pgEdge node when `permit_software_updates` is `true`. |
| `etcd_version` | The etcd release every node is brought to. |

## How It Works

### What a Host Needs

The role first decides what each host needs, without changing anything:

- On a pgEdge node, every installed `pgedge-` package except `pgedge-release`
  is checked. On an HAProxy host, `haproxy` is checked. A package needs an
  update when a repository offers a newer version than the one installed.
  The role refreshes the APT package index on Debian; on RHEL, DNF refreshes
  its metadata as it asks.
- Where the collection runs etcd, the release a node's etcd binary reports is
  compared with `etcd_version`.
- Patroni reports both the version it runs and the version installed. A
  difference means an earlier update replaced Patroni without restarting it.
- A service whose executable or libraries were replaced on disk while it ran
  still runs the old software. The role finds those through
  `/proc/<pid>/maps`, the way `needrestart` does, for etcd, Postgres,
  pgBouncer and HAProxy.
- A service that should be running and is not, such as one a stopped run
  left down, needs a restart too.
- On each zone's primary, a Spock or Snowflake extension whose version in a
  database differs from the one its package ships is listed. A run that
  stopped after the packages and before the extensions leaves these.

The check for replaced files does not ask which package replaced them. When
you apply operating system updates yourself, such as a new OpenSSL or glibc,
every service still running the old libraries counts as needing a restart.
The next run with `permit_software_updates` then restarts those nodes and
proxies in the same order as a package update, even when no package the
collection installed has changed. The report lists them as still running
replaced software.

The role then reports every update it found and the order the hosts will go
in. A run with nothing to update reports `Nothing to update.` and changes
nothing.

### The pgEdge Nodes

The nodes go one at a time. The zones go in order, and within a zone the
replicas that need an update go first, in inventory order. The zone's leader
goes last, so an updated replica is ready to take over when its turn comes.

For each node, the role:

1. Downloads `etcd_version` when the node has another release, while the
   node still serves its zone, so the download is never part of the outage.
2. Makes sure every other member of the zone is running or streaming. A run
   that finds a member down stops, rather than take a second member out.
3. Switches the zone's leader over, when the node leads its zone. Patroni
   chooses the new leader among the replicas, which are all updated by then.
4. Stops Patroni, which stops Postgres. On a simple cluster, stops Postgres.
5. Makes sure every member of the zone's etcd is healthy, stops etcd, installs
   the release downloaded in the first step, starts etcd, and waits until
   every member is healthy again.
6. Updates the node's packages.
7. Starts Patroni or Postgres, and restarts pgBouncer where the cluster pools
   connections.
8. Waits until the node streams from its zone's leader again, or on a simple
   cluster until Postgres accepts connections.

Services are stopped before any package replaces their files. No package
script restarts a service while the run is working on another node, and
etcd's binary is never replaced while it runs.

etcd goes with everything else on the node, not in a pass of its own. Patroni
reaches the store through its own node's etcd, so updating etcd on a leader in
place would risk the leader's lock. Updating it while the node is a replica
costs the zone nothing, and one member at a time keeps its quorum.

### Extensions

When every node is updated, the role compares each Spock and Snowflake
extension with the version its package ships, in every database in
`db_names`, and runs `ALTER EXTENSION ... UPDATE` on each zone's primary
where they differ. DDL replication is turned off for the statement, because
every zone updates its own. Replicas take the change by physical
replication. Most minor releases ship no new extension version, and then
there is nothing to do.

An extension whose package offers no update path from the installed version,
as when the package was rolled back to an earlier release outside the
collection, is left as it is. The report and a warning name it, and the run
goes on to HAProxy and pgBackRest.

Spock is compatible across minor versions, and with the next major version,
so zones that briefly run different minor releases keep replicating.

### HAProxy

The HAProxy hosts are updated and restarted one at a time, after every pgEdge
node. A zone's clients see their connections through its proxy dropped while
it restarts.

### pgBackRest

pgBackRest goes last, on every pgEdge node and backup server at the same
time. A pgBackRest client and the repository host it reaches over SSH refuse
each other unless their versions match exactly. WAL archiving fails between
two hosts from the moment one has the new version until the other does, and
updating them together keeps that window as short as it can be. Postgres
keeps every segment it could not archive and tries again, so nothing is lost.

On RHEL, the package gives `/var/log/pgbackrest` back to its own owner when
it is updated. The role then returns the directory to the user that runs
pgBackRest: `backup_repo_user` on a backup server and `postgres` on a pgEdge
node with a backup repository, as `setup_backrest` sets it.

The role refuses to update pgBackRest while a backup is running anywhere in
the cluster, because the update would make it fail. Everything else is
updated by then, and a later run updates pgBackRest. A scheduled backup can
still start in the moment between the check and the update; it fails, and the
next scheduled one runs as usual.

### Resuming

A run that stops partway, whether a zone member was down or a host failed,
can be run again. Every run starts by finding what each host needs, so the
next run skips what is done. A node whose packages were updated but whose
services were left stopped or running the old software is restarted, and an
extension update that never ran runs then.

Some changes an update makes are repaired straight after it, and a run
cancelled in between would leave them behind with nothing left to update on
that host. The role puts these right at the start of every run with the gate
set, before it looks for updates: today, the owner and mode of
`/var/log/pgbackrest`. A host that is already right is left unchanged. The
same repairs can run on their own, from a playbook of your own, with
`tasks_from: cleanup`:

```yaml
- hosts: pgedge:backup
  collections:
    - pgedge.platform
  tasks:
    - include_role:
        name: update_software
        tasks_from: cleanup
```

## Idempotency

A run with `permit_software_updates` set and nothing to update changes
nothing. A run without it does nothing at all.
