"""Prepare LAN certificates using the existing CA, identities and credentials."""
import argparse
import base64
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def firewall_plan(address, subnet):
    excluded = [ipaddress.IPv4Network("127.0.0.0/8"), ipaddress.IPv4Network(subnet)]
    blocks = [ipaddress.IPv4Network("0.0.0.0/0")]
    for exclusion in excluded:
        updated = []
        for block in blocks:
            updated.extend(block.address_exclude(exclusion) if exclusion.subnet_of(block) else [block])
        blocks = updated
    return {"ip": address, "subnet": subnet, "ports": [5601, 8443, 9200, 8000],
            "blocked_remote_ranges": [str(block) for block in blocks]}


def reissue_certificate(certificate, ca, ca_key, address, extra_dns=()):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    old = x509.load_pem_x509_certificate(certificate.encode())
    builder = (x509.CertificateBuilder().subject_name(old.subject).issuer_name(ca.subject)
               .public_key(old.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(old.not_valid_before_utc).not_valid_after(old.not_valid_after_utc))
    names = [x509.DNSName("localhost"), *(x509.DNSName(name) for name in extra_dns),
             x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.IPAddress(ipaddress.ip_address(address))]
    for extension in old.extensions:
        if isinstance(extension.value, x509.SubjectAlternativeName):
            names.extend(extension.value)
        elif not isinstance(extension.value, (x509.AuthorityKeyIdentifier, x509.BasicConstraints, x509.KeyUsage)):
            builder = builder.add_extension(extension.value, extension.critical)
    builder = (builder.add_extension(x509.SubjectAlternativeName(list(dict.fromkeys(names))), critical=False)
               .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
               .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
               .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False))
    return builder.sign(ca_key, hashes.SHA256())


def configure(address, subnet):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    if not (security.ROOT / "secrets/nifi-migration-state.json").is_file():
        raise RuntimeError("Pause NiFi with configure_nifi.py pause before preparing the certificates")
    values = security.decrypt()
    original = security.ENCRYPTED.read_bytes()
    backup_dir = security.ROOT / "secrets/backups"
    security.secure_directory(backup_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (backup_dir / f"secrets-before-lan-{stamp}.enc.json").write_bytes(original)
    old_pin = security.ROOT / "config/nifi-server.crt"
    if old_pin.exists():
        (backup_dir / f"nifi-certificate-before-lan-{stamp}.crt").write_bytes(old_pin.read_bytes())
    ca = x509.load_pem_x509_certificate(values["TLS_CA_CERT"].encode())
    ca_key = serialization.load_pem_private_key(values["TLS_CA_KEY"].encode(), password=None)
    for service in ("ELASTICSEARCH", "KIBANA", "SCORING"):
        cert = reissue_certificate(values[f"TLS_{service}_CERT"], ca, ca_key, address)
        cert.verify_directly_issued_by(ca)
        values[f"TLS_{service}_CERT"] = cert.public_bytes(serialization.Encoding.PEM).decode()

    # Read the existing NiFi store/password only into memory; keep its key, alias
    # and password so the persisted nifi.properties needs no secret changes.
    raw_properties = security.captured(["docker", "exec", "cnc-nifi", "cat", "/opt/nifi/nifi-current/conf/nifi.properties"])
    properties = dict(line.split("=", 1) for line in raw_properties.decode().splitlines()
                      if line and not line.startswith("#") and "=" in line)
    password = properties["nifi.security.keystorePasswd"].encode()
    store_path = properties["nifi.security.keystore"]
    if not store_path.startswith("/"):
        store_path = "/opt/nifi/nifi-current/" + store_path.removeprefix("./")
    if properties["nifi.security.keystoreType"].upper() != "PKCS12":
        raise RuntimeError("Expected a PKCS12 NiFi keystore; existing configuration kept")
    binary = security.captured(["docker", "exec", "cnc-nifi", "cat", store_path])
    store = pkcs12.load_pkcs12(binary, password)
    existing_cert = store.cert.certificate.public_bytes(serialization.Encoding.PEM).decode()
    cert = reissue_certificate(existing_cert, ca, ca_key, address, extra_dns=("nifi", "cnc-nifi"))
    cert.verify_directly_issued_by(ca)
    values["TLS_NIFI_CERT"] = cert.public_bytes(serialization.Encoding.PEM).decode()
    values["NIFI_KEYSTORE_P12"] = base64.b64encode(pkcs12.serialize_key_and_certificates(
        store.cert.friendly_name or b"nifi-key", store.key, cert, [ca],
        serialization.BestAvailableEncryption(password))).decode()
    security.validate(values)
    recipient = security.captured(["age-keygen", "-y", os.environ["SOPS_AGE_KEY_FILE"]]).decode().strip()
    encrypted = security.captured(["sops", "encrypt", "--age", recipient, "--input-type", "json",
                                   "--output-type", "json", "--filename-override", str(security.ENCRYPTED)],
                                  data=json.dumps(values).encode())
    temporary = security.ENCRYPTED.with_suffix(".tmp")
    temporary.write_bytes(encrypted)
    restored = json.loads(security.captured(["sops", "decrypt", "--output-type", "json", str(temporary)]))
    if restored != values or security.ENCRYPTED.read_bytes() != original:
        raise RuntimeError("Encrypted update verification failed or vault changed concurrently")
    temporary.replace(security.ENCRYPTED)
    (security.ROOT / "config/lan.json").write_text(json.dumps({"ip": address, "subnet": subnet}, indent=2) + "\n")
    old_pin.write_text(values["TLS_NIFI_CERT"], encoding="ascii")
    security.materialize(values, security.runtime_path())
    print("Updated all four certificates for the server IP using the existing CA; passwords and private service keys preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "configure"))
    parser.add_argument("--ip", required=True)
    parser.add_argument("--subnet", required=True)
    args = parser.parse_args()
    address, network = ipaddress.IPv4Address(args.ip), ipaddress.IPv4Network(args.subnet, strict=True)
    if address not in network or address.is_loopback or not address.is_private:
        raise ValueError("Choose the server's private IPv4 address and its actual subnet")
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    if args.command == "plan":
        plan = firewall_plan(str(address), str(network))
        (security.ROOT / "config/lan-firewall.json").write_text(json.dumps(plan, indent=2) + "\n")
        print("Prepared LAN-only firewall plan for TCP ports 5601, 8443, 9200 and 8000.")
    else:
        configure(str(address), str(network))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f"LAN setup failed: {error}", file=sys.stderr)
        sys.exit(1)
