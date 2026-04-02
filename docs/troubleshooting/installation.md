# Collection Installation

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
available on the control node. Check that the `VERSION` file exists in the
repository root. If the file is missing, pull the latest changes with
`git pull` and retry.

## SSH Connection Failure

**Symptom:** Ansible cannot connect to target hosts.

**Solution:** Test connectivity from the control node to a target host:

```bash
ssh -i ~/.ssh/your_key user@target-host
ansible all -m ping -i inventory.yaml
```

Ensure that the target host accepts connections from the control node and
that the inventory specifies the correct `ansible_user` and SSH key.
