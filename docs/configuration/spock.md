# Spock Configuration

These parameters control how the Spock extension handles replication behavior
in your pgEdge cluster.

## exception_behaviour

- Type: String
- Default: `transdiscard`
- Options: `discard`, `transdiscard`, `sub_disable`
- Description: This parameter defines how Spock handles replication exceptions
  when they occur during data synchronization. The available options provide
  different levels of intervention:

  - `discard` skips only the offending statement and continues replication.
  - `transdiscard` skips the entire offending transaction and continues.
  - `sub_disable` disables the subscription and requires manual intervention
    to re-enable it.

See the
[Spock documentation](https://docs.pgedge.com/platform/exception#spockexception_behaviour)
for detailed information about exception handling behavior.

In the following example, the inventory sets the exception behavior to discard
transactions:

```yaml
pgedge:
  vars:
    exception_behaviour: transdiscard
```

## pgedge_join_zones

- Type: List of integers
- Default: none
- Description: This parameter names the zones to join to a cluster that
  already holds data, in the order they should join. Each zone must be in the
  inventory. The deployment copies every database in `db_names` into each
  zone in turn, while the existing zones keep taking writes, and then makes it
  a full member of the cluster. A listed zone that is already a member is
  reported and skipped. Pass it on the command line rather than in the
  inventory, and use it only on a cluster that already holds data: a run with
  it refuses to start when no database holds data yet. Without it, a run
  refuses a zone that is in the inventory but not yet part of a cluster that
  holds data. See [Adding a Zone to a Running Cluster](../add_zone.md).

The following examples join zone 4, and then zones 4 and 5 in that order:

```bash
ansible-playbook -i inventory.yaml playbook.yaml -e pgedge_join_zones=4
ansible-playbook -i inventory.yaml playbook.yaml -e pgedge_join_zones=4,5
ansible-playbook -i inventory.yaml playbook.yaml -e '{"pgedge_join_zones": [4, 5]}'
```

A bracketed list given as a plain argument, such as
`-e pgedge_join_zones=[4]`, reaches Ansible as text, and the run refuses it.

## pgedge_join_wait_minutes

- Type: Integer
- Default: `30`
- Description: This parameter sets how long a join waits, in minutes, for a
  zone to apply a bookmark another zone has set, and for each new
  subscription to start replicating. A join uses these waits to confirm that
  every write has arrived before it moves on, and they normally take seconds.
  A wait that runs out fails the join in a way that the same command, run
  again, resumes. The copy itself is governed by `pgedge_seed_stall_minutes`
  and `pgedge_seed_max_hours` instead.

## pgedge_seed_zone

- Type: Integer
- Default: none
- Description: This parameter is for recovery only. In an HA cluster, it names
  a zone that already holds the cluster's data while every other zone is
  empty and takes no writes. The empty zones copy the seed zone's schema and
  data before the rest of the subscriptions are created. The recovery
  playbook sets it to the zone it restores; an ordinary deployment leaves it
  unset. To add a zone to a cluster that is running, use `pgedge_join_zones`
  instead. A run given both refuses to start.

## pgedge_seed_stall_minutes

- Type: Integer
- Default: `15`
- Description: This parameter sets how long a Spock copy may go without
  progress before the role gives up, in minutes. It applies to the copy from
  `pgedge_seed_zone` in a recovery and to the copy a zone named in
  `pgedge_join_zones` makes from an existing zone. Progress is any change in
  the sync step, the tables left to sync, the database's size, or the COPY and
  index-build progress Postgres reports. The role gives up sooner if Spock
  disables the subscription or its apply worker stays down for two minutes.
  The limit applies to each database in `db_names` separately. A join that
  gives up this way can be resumed by running the same command again, as long
  as Spock's copy is still going.

## pgedge_seed_max_hours

- Type: Integer
- Default: `24`
- Description: This parameter limits how long a Spock copy may take, in hours,
  for each database in `db_names` separately: the copy from `pgedge_seed_zone`
  in a recovery, or a joining zone's copy. It is a backstop, not an estimate:
  the copy takes as long as the database is large.
