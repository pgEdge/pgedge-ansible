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
