# Spock Configuration

These parameters modify how the Spock extension itself operates.

## exception_behaviour

- Type: String
- Default: `transdiscard`
- Options: `discard`, `transdiscard`, `sub_disable`
- Description: This parameter defines Spock's behavior when encountering replication exceptions.

    - `discard` - Skip the offending statement
    - `transdiscard` - Skip the offending transaction
    - `sub_disable` - Disable the subscription for manual intervention

See the [Spock documentation](https://docs.pgedge.com/spock-v5/install_spock/#spockexception_behaviour) for details.

```yaml
exception_behaviour: transdiscard
```
