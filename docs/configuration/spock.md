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

## pgedge_seed_zone

- Type: Integer
- Default: none
- Description: In an HA cluster, this parameter names a zone that already
  holds the cluster's data while every other zone is empty. The empty zones
  copy the seed zone's schema and data before the rest of the subscriptions
  are created. The recovery playbook sets it to the zone it restores; an
  ordinary deployment leaves it unset.

## pgedge_seed_max_hours

- Type: Integer
- Default: `24`
- Description: This parameter limits how long the copy from
  `pgedge_seed_zone` may take, in hours. It is a backstop, not an estimate:
  the copy takes as long as the database is large.
