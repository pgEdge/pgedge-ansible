#!/usr/bin/env python3
"""Render setup_backrest's pgbackrest.conf offline for both cipher types.

The live matrix deploys one encrypted repository, so an unencrypted one --
backup_repo_cipher_type: none, for storage that encrypts at rest itself -- is
never rendered anywhere a run would notice. PgBackRest refuses a configuration
that sets a cipher password with no cipher, and a configuration that names a
cipher with no password cannot read its own repository, so each render has to
carry the password exactly when it encrypts.

Whether it encrypts is decided by role_config's backup_repo_encrypted, and that
expression is read out of role_config's own vars here rather than restated, so
this also pins the derivation the template depends on.

Every host that renders the file is covered: a pgEdge node and a backup server
for an SSH repository, and a pgEdge node for an S3 one -- with
role_config's S3 defaults, which must leave PgBackRest's own URI style and CA
bundle, port and certificate checks alone, and set up the ways an S3-compatible
store such as MinIO needs: path-style addressing on its own port with a private
CA, and with certificate checks off for a test store.
"""

import configparser
import sys
from pathlib import Path

import yaml
from jinja2 import (Environment, FileSystemLoader, StrictUndefined,
                    select_autoescape)

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO / "roles" / "setup_backrest" / "templates"
ROLE_VARS = REPO / "roles" / "role_config" / "vars" / "main.yaml"

NODES = ["10.0.0.10", "10.0.0.11", "10.0.0.12"]
BACKUP = ["10.0.0.18"]
CIPHER = "TestCipher987"

# What an inventory gives backup_repo_params for each S3 case. Laid over
# role_config's default_repo_params the way the role's combine does, so a key
# role_config adds without the template knowing it fails a StrictUndefined
# render rather than passing unnoticed.
S3_PARAMS = {
    "s3": {"endpoint": "s3.example.com", "bucket": "b", "access_key": "k",
           "secret_key": "s"},
    "minio": {"endpoint": "minio.example.com", "bucket": "b",
              "access_key": "k", "secret_key": "s", "uri_style": "path",
              "storage_ca_file": "/etc/pki/minio-ca.crt",
              "storage_port": 9000},
    # A test store with a self-signed certificate. storage_verify_tls is a YAML
    # boolean in the inventory, and false must still render, as n rather than
    # nothing.
    "minio-insecure": {"endpoint": "minio.example.com", "bucket": "b",
                       "access_key": "k", "secret_key": "s",
                       "uri_style": "path", "storage_verify_tls": False},
}

# What each S3_PARAMS case must render for the options that are omitted unless
# set, keyed by option name. Anything not listed must be absent.
S3_EXPECTED = {
    "minio": {"repo1-s3-uri-style": "path",
              "repo1-storage-ca-file": "/etc/pki/minio-ca.crt",
              "repo1-storage-port": "9000"},
    "minio-insecure": {"repo1-s3-uri-style": "path",
                       "repo1-storage-verify-tls": "n"},
}
OPTIONAL_S3 = ("repo1-s3-uri-style", "repo1-storage-ca-file",
               "repo1-storage-port", "repo1-storage-verify-tls")


def env():
    # Not autoescaped and strict about undefined variables, for the reasons
    # check-patroni.py gives: Ansible's template module does neither, and
    # trim_blocks is on there too.
    e = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                    autoescape=select_autoescape(enabled_extensions=(),
                                                 default_for_string=False,
                                                 default=False),
                    undefined=StrictUndefined,
                    trim_blocks=True, keep_trailing_newline=True)
    e.filters["bool"] = lambda v: str(v).strip().lower() in (
        "true", "yes", "on", "1")
    return e


def encrypted(e, cipher_type):
    """role_config's backup_repo_encrypted, evaluated as Ansible would."""
    expr = yaml.safe_load(ROLE_VARS.read_text())["backup_repo_encrypted"]
    return e.from_string(expr).render(backup_repo_cipher_type=cipher_type)


def repo_params(flavour):
    """role_config's backup_params for one of the S3_PARAMS cases."""
    defaults = yaml.safe_load(ROLE_VARS.read_text())["default_repo_params"]
    return {**defaults, **S3_PARAMS.get(flavour, {})}


def context(e, cipher_type, flavour, host):
    backup_type = "ssh" if flavour == "ssh" else "s3"
    return dict(
        backup_stanza="pgedge-demo-1", inventory_hostname=host,
        groups={"pgedge": NODES, "backup": BACKUP},
        hostvars={h: {"inventory_hostname": h} for h in NODES + BACKUP},
        nodes_in_zone=NODES, pg_port=5432, pg_data="/var/lib/pgsql/17/data",
        backup_repo_path="/var/lib/pgbackrest", full_backup_count=1,
        diff_backup_count=6, backup_repo_cipher_type=cipher_type,
        backup_repo_encrypted=encrypted(e, cipher_type),
        # init_server refuses a password where nothing encrypts, so a valid
        # inventory with cipher type none has an empty one.
        backup_repo_cipher=CIPHER if cipher_type != "none" else "",
        backup_type=backup_type, backup_server=BACKUP[0],
        backup_repo_user="backrest",
        backup_params=repo_params(flavour))


def failed_checks(text, cipher_type, flavour):
    ini = configparser.ConfigParser(interpolation=None)
    ini.read_string(text)
    g = ini["global"]
    checks = {
        "cipher type": g.get("repo1-cipher-type") == cipher_type,
        "cipher password exactly when encrypting":
            ("repo1-cipher-pass" in g) == (cipher_type != "none"),
        "cipher password is the configured one":
            cipher_type == "none" or g.get("repo1-cipher-pass") == CIPHER,
    }
    # Set exactly where the inventory set them, and absent otherwise.
    for option in OPTIONAL_S3:
        checks[option] = (g.get(option)
                          == S3_EXPECTED.get(flavour, {}).get(option))
    return [name for name, ok in checks.items() if not ok]


def main():
    e = env()
    template = e.get_template("pgbackrest.conf.j2")
    failures = []

    cases = [("ssh", NODES[0], "ssh node"), ("ssh", BACKUP[0], "ssh server"),
             ("s3", NODES[0], "s3 node"), ("minio", NODES[0], "minio node"),
             ("minio-insecure", NODES[0], "insecure minio node")]
    for cipher_type in ("aes-256-cbc", "none"):
        for flavour, host, where in cases:
            label = f"{cipher_type:<12} {where}"
            try:
                text = template.render(**context(e, cipher_type, flavour,
                                                 host))
                bad = failed_checks(text, cipher_type, flavour)
            except Exception as exc:
                bad = [f"{type(exc).__name__}: {exc}"]
            if bad:
                failures.append(f"{label}: {', '.join(bad)}")
                print(f"FAIL     {label}: {', '.join(bad)}")
            else:
                print(f"ok       {label}")

    if failures:
        print("\n" + "\n".join(f"  - {f}" for f in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
