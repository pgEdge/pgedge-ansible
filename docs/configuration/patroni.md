# Patroni Configuration

The following settings define how Patroni operates. The `install_patroni` and
`setup_patroni` roles use these settings to configure the HA management layer.

## patroni_tls_dir

- Type: String
- Default: `/etc/patroni/tls`
- Description: This parameter specifies the directory where the roles install
  Patroni TLS certificates necessary for communicating with etcd.

In the following example, the inventory specifies the Patroni TLS directory:

```yaml
patroni_tls_dir: "/etc/ssl/certs/patroni"
```
