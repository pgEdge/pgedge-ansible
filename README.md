# Engineering Test Environment Ansible Scripts

Due to the requirement of spinning up clusters on a regular basis, we've supplied a series of Ansible roles which will build a full pgEdge cluster when executed. These will be described here, along with any variables necessary to modify behavior or configuration characteristics.

## Configuration

All of the roles are meant to operate in conjunction. They are simplified to reduce complexity and add potential for more complex cluster deployments. Roles will collectively recognize the following configuration parameters:

| **Parameter** | **Default** | **Description**                                     |
|---------------|-------------|-----------------------------------------------------|
| repo_name | download | Can be one of `download`, `upstream`, or `devel`. This will control which pgEdge repository is used for software installation. |
| zone | 1 | Zone or region for a node. This helps organize HA clusters. It also doubles as the snowflake ID of a node. For non-HA clusters, just use one node per zone. |
| pg_version | 16 | Postgres version to install. This is left at 16 to facilitate upgrade tests. |
| spock_version | 4.0.9 | Version of the Spock extension to install. |
| db_name | demo | Name of the database to use for the Spock cluster. |
| db_user | admin | Database username. Must be something other than `pgedge`. Note that the CLI will create a `pgedge` user for its own purposes as part of the installation and setup process. |
| db_password | secret | Password for the `db_user` user. |
| is_ha_cluster | false | If true, install etcd and Patroni on all nodes in the `pgedge` group. If HAProxy nodes exist, they will reflect nodes in the same zone. Subscriptions from other pgEdge nodes will also pass through the zone HAProxy. |
| replication_user | replicator | This user is specifically for Patroni replication purposes. |
| replication_password | secret | Password for the `replication_user` user. |
| synchronous_mode | false | Enable to allow Patroni to manage `synchonous_commit` and `synchronous_standby_names` parameters based on HA cluster state. |
| synchronous_mode_strict | false | When synchronous mode is enabled, Patroni will normally disable synchronous replication if no synchronous replicas are available. Enable this parameter to always enforce synchronous commit. |

Modifying other parameters will have no effect on the cluster.

## Role Variables

The roles described here often make use of shortcut variables internally. If seeking to modify these roles, these variables may prove useful. To augment configurability, some of these may be moved to be role defaults rather than variables.

Notable items are listed here:

| **Variable**  | **Value**   | **Description**                                     |
|---------------|-------------|-----------------------------------------------------|
| repo_url | https://pgedge-$repo.s3.amazonaws.com/REPO | This is based on the sanitized value of the `repo` role parameter. |
| cluster_path | `$HOME/pgedge` | In most cases, this is `/home/pgedge/pgedge`. This is the default location where the CLI will install itself. |
| pg_path | `$cluster_path/pg${version}` | For a Postgres 16 install, this will likely be `/home/pgedge/pgedge/pg16`. |
| pg_data | `$cluster_path/data/pg${version}` | For a Postgres 16 install, this will likely be `/home/pgedge/pgedge/data/pg16`. |
| nodes_in_zone | Node list | Should be a list of all nodes in the `pgedge` group which are in the same zone as this node. Used in several roles for service configuration. |

## Role List

The full list of roles is as follows, in the expected order of execution:

1. `init_server` - Prepares each server in the cluster to operate in the stack. This should be executed on every available server.
2. `install_pgedge` - Only installs the `pgedge` CLI software, and does nothing else.
3. `setup_postgres` - Uses the CLI software `setup` command to create a Postgres instance on each node. This will also install the snowflake and spock extensions. In HA clusters, multiple nodes can be assigned to each zone. Of these, all but the first will have the Postgres stopped, and the data directory wiped. This is a preparation step for Patroni.
4. `install_etcd` - Only used for HA clusters. Uses the CLI to download and install the version of etcd packaged by pgEdge. The service is not yet configured or started.
5. `install_patroni` - Only used for HA clusters. Uses the CLI to download and install the version of etcd packaged by pgEdge. The service is not yet configured or started.
6. `setup_etcd` - Only used for HA clusters. Fully configures etcd on each node. Nodes in the `pgedge` group in same zone are configured to be part of the same etcd quorum. In zones with fewer than 3 nodes, etcd will still function, but will require all nodes to be operational to maintain quorum.
7. `setup_patroni` - Only used for HA clusters. Fully configures patroni on each node. Nodes in the `pgedge` group in the same zone are configured to be part of the same Patroni cluster. The first node in the list is used to bootstrap Patroni itself, and Patroni will rebuild all other Postgres instances in the zone from this.
8. `setup_haproxy` - Only used for HA clusters. This should be executed before `setup_pgedge`, as HA clusters are intended to communicate through the proxy layer so subscriptions survive failover events.
9. `setup_pgedge` - Establishes a pgEdge node for all nodes in the `pgedge` group. Also subscribes each node to every other node. Will additionally set the snowflake node ID to be the same as the zone, so use the zone as a logical node identifier. In HA clusters, node creation only takes place once per zone. HA clusters are also subscribed to either the first HAProxy node in the same zone as the remote pgEdge node, or if this is missing, the first pgEdge node in that zone. This allows for "hybrid" clusters for simplified testing, where a single pgEdge node interacts with a Patroni-managed sub-cluster.

## Usage

There are a few files which illustrate how these roles should be utilized:

* `inventory.yaml` - A sample cluster with three pgEdge nodes.
* `sample-playbook.yaml` - Calls the roles in the appropriate order to produce a standard pgEdge cluster.
* `inventory-ha.yaml` - A sample HA cluster with two zones, three pgEdge nodes in each zone, and one HAProxy node per zone. This is a total of eight nodes.
* `sample-playbook-ha.yaml` - Calls the roles in the appropriate order, with expected node groups, to produce a fully operational HA cluster.

## Notes

These roles are very early in their life, and will likely undergo heavy revision as they mature. They are fairly fragile, and not fully re-entrant if they encounter an unexpected error. This situation will improve with time if we continue using them for testing.
