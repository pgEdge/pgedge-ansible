# Installation Issues

This page covers issues that block cluster deployment before it begins.

## Collection Not Found

**Symptom:** Ansible reports that the `pgedge.platform` collection is not
found.

**Solution:** Verify that the collection installed correctly by running the
following command:

```bash
ansible-galaxy collection list pgedge.platform
```

If the collection is missing, reinstall it from the repository:

```bash
cd pgedge-ansible
make install
```

## Build Failure

**Symptom:** The `make install` command fails.

**Solution:** Ensure that Ansible and the `ansible-galaxy` command are
available on the control node.

If the build stops with `Cannot tell which version this is`, the source tree
has neither git tags nor a version recorded by `git archive`. That happens with
a plain copy of the files, or a clone made without its tags. Fetch the tags with
`git fetch --tags`, or name the version yourself:

```bash
make install VERSION=2.0.0
```

## SSH Connection Failure

**Symptom:** Ansible cannot connect to target hosts.

**Solution:** Test connectivity from the control node to a target host:

```bash
ssh -i ~/.ssh/your_key user@target-host
ansible all -m ping -i inventory.yaml
```

Ensure that the target host accepts connections from the control node and
that the inventory specifies the correct `ansible_user` and SSH key.
