# Solving Collection Installation Issues

When deploying pgEdge clusters with Ansible, installation issues can block
progress before deployment begins. These problems typically stem from improper
collection installation, missing dependencies, or connectivity challenges
between the control node and managed hosts. Ansible may fail to locate the
collection despite successful installation, or build processes may fail due to
missing prerequisites.

SSH connection issues are particularly common, especially when working with new
environments or strict security policies. This section addresses these
foundational challenges and provides step-by-step solutions to ensure the
automation environment is properly configured and operational before proceeding
with cluster deployment.

## Collection Not Found

If Ansible cannot find the collection after installation:

1. Check the installation path with the following command:

   ```bash
   ansible-galaxy collection list
   ```

2. Verify the collections path in the `ansible.cfg` file:

   ```ini
   [defaults]
   collections_paths = ~/.ansible/collections:/usr/share/ansible/collections
   ```

## Build Failures

If `make install` fails, check the following items:

- Ensure the `ansible-galaxy` command is available in the system PATH.
- Check that the user has write permissions to the collections directory.
- Verify the `VERSION` file exists in the repository root directory.

## SSH Connection Issues

If Ansible cannot connect to hosts, check the following items:

- Verify SSH access manually by running `ssh user@host`.
- Check SSH key permissions by running `chmod 600 ~/.ssh/id_rsa`.
- Ensure the remote user has appropriate sudo privileges.
- Review the inventory file for correct hostnames and connection settings.
