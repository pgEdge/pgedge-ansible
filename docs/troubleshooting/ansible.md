# Solving Ansible Execution Issues

Ansible execution problems often indicate foundational issues with
connectivity, playbook syntax, or role dependency management. When playbooks
fail to execute correctly, diagnosing the root cause requires examining
execution logs, testing connectivity between the control node and targets, and
verifying inventory configurations.

Problems may stem from permission issues, missing tags, or incorrect execution
order of roles. This section provides essential troubleshooting techniques for
Ansible-specific execution challenges that prevent successful automation of
your pgEdge cluster deployment processes.

## Playbook Failures

Playbook failures can result from syntax errors, undefined variables, or task
execution problems.

Increase verbosity to capture detailed execution information:

```bash
ansible-playbook playbook.yaml -vvv
```

Use check mode to perform a dry run without making changes:

```bash
ansible-playbook playbook.yaml --check
```

## Connection Issues

Connection issues prevent Ansible from communicating with target hosts.

Test connectivity to all hosts in the inventory:

```bash
ansible all -i inventory.yaml -m ping
```

Verify SSH access and command execution on remote hosts:

```bash
ansible all -i inventory.yaml -m shell -a "hostname"
```

## Check Mode Limitations

Check mode cannot validate tasks that depend on changes from previous tasks.

**Symptom:** Tasks fail in check mode even though they succeed during normal 
execution.

**Solution:**

Ansible considers this behavior expected when tasks depend on 
changes from previous tasks; run the playbook without check mode to verify 
functionality.

## Debugging Individual Roles

Isolating a specific role helps identify which role causes failures.

Run a specific role in isolation using tags:

```bash
ansible-playbook playbook.yml --tags role_name
```

## Role Dependencies Not Met

Role dependency failures occur when prerequisite roles have not completed
successfully.

**Symptom:** A role fails because a required service, file, or configuration 
does not exist.

**Solution:**

- Verify that prerequisite roles completed successfully and the inventory
  defines all required variables.
- Ensure that your playbook executes roles in the proper order.
- Verify that prerequisite roles completed without errors.
- Check that your inventory defines all required variables for each role.

## Getting Help

If you encounter issues not covered in this guide, the following resources can
provide additional assistance.

1. Check the [GitHub repository](https://github.com/pgEdge/pgedge-ansible) for
   known issues and existing solutions.
2. Review role-specific documentation in the
   [roles section](../roles/index.md) for configuration requirements.
3. Examine system logs on target hosts for detailed error messages.
4. Open an issue on GitHub with detailed information about your environment
   and the problem you encountered.
