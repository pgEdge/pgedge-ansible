# Spock Configuration

These parameters control how the Spock extension handles replication behavior
in your pgEdge cluster.

## exception_behaviour

This parameter defines how Spock handles replication exceptions when they occur
during data synchronization.

| Attribute | Value |
|-----------|-------|
| Type | String |
| Default | `transdiscard` |
| Options | `discard`, `transdiscard`, `sub_disable` |

The available options provide different levels of intervention:

- The `discard` option skips only the offending statement.
- The `transdiscard` option skips the entire offending transaction.
- The `sub_disable` option disables the subscription for manual intervention.

See the
[Spock documentation](https://docs.pgedge.com/spock-v5/install_spock/#spockexception_behaviour)
for detailed information about exception handling behavior.

In the following example, the inventory sets the exception behavior to
discard transactions:

```yaml
pgedge:
  vars:
    exception_behaviour: transdiscard
```
