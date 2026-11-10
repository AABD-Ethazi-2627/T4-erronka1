"""Windows Docker Desktop and Linux deployment using SOPS + age.

Runtime files use Windows ACLs or Linux tmpfs permissions. Never source
decrypted configuration as shell code or pass passwords on command lines.
"""
import argparse
import base64
import csv
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENCRYPTED = ROOT / "config/secrets.enc.json"
SECRET_NAMES = (
    "NIFI_PASSWORD", "MONGO_PASSWORD", "SMB_PASSWORD", "ELASTIC_PASSWORD",
    "KIBANA_SYSTEM_PASSWORD", "KIBANA_PASSWORD", "NIFI_ELASTIC_PASSWORD",
    "SCORING_API_TOKEN", "KIBANA_SECURITY_KEY", "KIBANA_SAVED_OBJECTS_KEY",
    "KIBANA_REPORTING_KEY",
)
REQUIRED = (*SECRET_NAMES, "NIFI_USERNAME", "MONGO_USERNAME", "SMB_USERNAME",
            "KIBANA_USERNAME", "TLS_CA_CERT", "TLS_CA_KEY",
            "TLS_ELASTICSEARCH_CERT", "TLS_ELASTICSEARCH_KEY",
            "TLS_KIBANA_CERT", "TLS_KIBANA_KEY", "TLS_SCORING_CERT", "TLS_SCORING_KEY")


def secure_directory(path):
    """Restrict a directory before writing any secrets into it."""
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("Secret directories cannot be links or junctions")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sys.platform == "win32":
        identity = captured(["whoami", "/user", "/fo", "csv", "/nh"]).decode("utf-8", errors="replace")
        sid = next(csv.reader([identity.strip()]))[-1]
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise RuntimeError("Cannot determine the current Windows user SID")
        # Replace the ACL, including existing explicit entries. Inheritance on
        # children keeps Docker Desktop (this user or SYSTEM) able to read files.
        script = (
            "$acl = New-Object System.Security.AccessControl.DirectorySecurity; "
            "$acl.SetAccessRuleProtection($true, $false); "
            "foreach ($sid in @($env:CNC_ACL_USER_SID, 'S-1-5-18')) { "
            "$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("
            "(New-Object System.Security.Principal.SecurityIdentifier($sid)), "
            "'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'); "
            "$acl.AddAccessRule($rule) }; "
            "[System.IO.Directory]::SetAccessControl($env:CNC_ACL_DIRECTORY, $acl)"
        )
        env = dict(os.environ, CNC_ACL_USER_SID=sid, CNC_ACL_DIRECTORY=str(path.resolve()))
        captured(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "$ErrorActionPreference = 'Stop'; " + script], env=env)
    else:
        if path.stat().st_uid != os.getuid():
            raise ValueError("Secret directory belongs to another user")
        path.chmod(0o700)


def default_age_key():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "CNCGuard/age/keys.txt"
    return Path.home() / ".config/sops/age/keys.txt"


def doctor():
    """Report process/path access failures without reading secret contents."""
    report = {"python": sys.executable, "platform": sys.platform, "cwd": str(Path.cwd())}
    if sys.platform == "win32":
        result = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"], capture_output=True)
        report["identity"] = result.stdout.decode(errors="replace").strip()
    configured = os.environ.get("SOPS_AGE_KEY_FILE", "").strip().strip('"')
    paths = {"default": default_age_key()}
    if configured:
        paths["configured"] = Path(os.path.expandvars(configured)).expanduser()
    report["key_access"] = {}
    for name, path in paths.items():
        entry = {"path": str(path)}
        try:
            # Open and immediately close; never read any key bytes for diagnostics.
            with path.open("rb"):
                pass
            entry["readable"] = True
        except OSError as error:
            entry.update(readable=False, error=type(error).__name__, errno=error.errno,
                         winerror=getattr(error, "winerror", None))
        report["key_access"][name] = entry
    report["ciphertext_exists"] = ENCRYPTED.is_file()
    report["windows_encrypted_recovery_exists"] = (ROOT / "secrets/recovery/age-key.dpapi").is_file()
    print(json.dumps(report, indent=2, ensure_ascii=True))


def restore_age_key():
    """Restore a missing identity from a same-user, same-machine DPAPI export."""
    if sys.platform != "win32":
        return False
    recovery = ROOT / "secrets/recovery/age-key.dpapi"
    try:
        if not recovery.is_file():
            return False
    except OSError:
        return False
    destination = default_age_key()
    if destination.exists():
        # Never replace an existing private identity, even if it is unreadable.
        return False
    script = (
        "$ErrorActionPreference = 'Stop'; Add-Type -AssemblyName System.Security; "
        "$encrypted = [System.IO.File]::ReadAllBytes($env:CNC_KEY_RECOVERY_FILE); "
        "$key = [System.Security.Cryptography.ProtectedData]::Unprotect("
        "$encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser); "
        "$output = [Console]::OpenStandardOutput(); $output.Write($key, 0, $key.Length); "
        "[Array]::Clear($key, 0, $key.Length)"
    )
    try:
        key = captured(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       env=dict(os.environ, CNC_KEY_RECOVERY_FILE=str(recovery)))
    except RuntimeError:
        raise RuntimeError(
            "Windows could not unlock the encrypted key recovery. It must be opened "
            "by the same Windows account on the same PC that created it. No key was changed."
        ) from None
    if b"AGE-SECRET-KEY-" not in key:
        raise RuntimeError("Invalid age key recovery; no key was written")
    secure_directory(destination.parent)
    with destination.open("xb") as output:
        output.write(key)
    return True


def captured(args, *, data=None, env=None):
    if sys.platform == "win32" and args[0] in ("sops", "age-keygen"):
        portable = Path(__file__).resolve().parents[1] / ".venv/security-tools" / (args[0] + ".exe")
        if portable.is_file():
            args = [str(portable), *args[1:]]
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=ROOT)
    if result.returncode:
        # Tools may include input values in diagnostics. Do not echo them.
        raise RuntimeError(f"{Path(args[0]).name} failed; check installation, permissions and keys")
    return result.stdout


def validate(values):
    if not isinstance(values, dict):
        raise ValueError("Encrypted configuration must contain a JSON object")
    for name in REQUIRED:
        if not isinstance(values.get(name), str) or not values[name].strip():
            raise ValueError(f"Missing non-empty secret: {name}")
    for name in SECRET_NAMES:
        minimum = 12 if name == "NIFI_PASSWORD" else 1 if name in ("SMB_PASSWORD", "MONGO_PASSWORD") else 32
        if len(values[name]) < minimum:
            raise ValueError(f"{name} must contain at least {minimum} characters")
    token = values["SCORING_API_TOKEN"]
    if not token.isascii() or any(c.isspace() for c in token):
        raise ValueError("SCORING_API_TOKEN must be ASCII without whitespace")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", values["KIBANA_USERNAME"]):
        raise ValueError("KIBANA_USERNAME must be a lowercase username, 3-64 characters")
    if values["KIBANA_USERNAME"] in ("elastic", "kibana_system", "cnc_nifi"):
        raise ValueError("KIBANA_USERNAME conflicts with a service or administrator account")
    # CIFS mount options are comma separated; commas cannot be safely interpolated.
    for name in ("SMB_USERNAME", "SMB_PASSWORD"):
        if any(c in values[name] for c in (",", "\n", "\r", "\x00")):
            raise ValueError(f"{name} contains characters unsupported by the CIFS volume")


def read_legacy_env(path):
    """Import simple dotenv values without ever executing shell expressions."""
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, raw = line.removeprefix("export ").partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
            raise ValueError("Unsupported dotenv line; use simple NAME=value entries")
        raw = raw.strip()
        if raw.startswith(("'", '"')):
            parts = shlex.split(raw, comments=True, posix=True)
            if len(parts) != 1:
                raise ValueError("Unsupported quoted dotenv value")
            value = parts[0]
        else:
            value = re.split(r"\s+#", raw, maxsplit=1)[0].rstrip()
        if "${" in value or (not raw.startswith("'") and "$" in value):
            raise ValueError("Dotenv interpolation is unsupported; use literal single-quoted values")
        values[name.strip()] = value
    return values


def make_pki():
    """Generate certificates entirely in memory, without a host OpenSSL install."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    except ImportError:
        raise RuntimeError("Install scripts/requirements-security.txt with your Python interpreter") from None
    import ipaddress

    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CNC Guard Local CA")])

    def builder(subject, public_key, days):
        return (x509.CertificateBuilder().subject_name(subject).issuer_name(ca_name)
                .public_key(public_key).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=days)))

    ca = (builder(ca_name, ca_key.public_key(), 1825)
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))

    def private_pem(key):
        return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                 serialization.NoEncryption()).decode("ascii")

    values = {"TLS_CA_KEY": private_pem(ca_key), "TLS_CA_CERT": ca.public_bytes(serialization.Encoding.PEM).decode("ascii")}
    for service, dns in (("elasticsearch", "elasticsearch"), ("kibana", "kibana"), ("scoring", "scoring-api")):
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, dns)])
        cert = (builder(subject, key.public_key(), 825)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(dns), x509.DNSName("localhost"),
                                                          x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        values[f"TLS_{service.upper()}_KEY"] = private_pem(key)
        values[f"TLS_{service.upper()}_CERT"] = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    return values


def init(import_env):
    if ENCRYPTED.exists():
        raise ValueError("Encrypted configuration already exists; use sops edit instead")
    if (ROOT / ".env").exists() and not import_env:
        raise ValueError("Existing .env found: use init --import-env .env to preserve credentials")
    previous = read_legacy_env(Path(import_env)) if import_env else {}
    values = {name: secrets.token_urlsafe(36) for name in SECRET_NAMES}
    values.update(NIFI_USERNAME="cncadmin", MONGO_USERNAME="mongoadmin",
                  KIBANA_USERNAME="cncviewer")
    for name in ("NIFI_USERNAME", "NIFI_PASSWORD", "MONGO_USERNAME", "MONGO_PASSWORD",
                 "SMB_USERNAME", "SMB_PASSWORD"):
        if previous.get(name):
            values[name] = previous[name]
    if not values.get("SMB_USERNAME"):
        values["SMB_USERNAME"] = input("SMB username: ").strip()
    if not values.get("SMB_PASSWORD"):
        values["SMB_PASSWORD"] = getpass.getpass("SMB password: ")
    key = Path(os.environ["SOPS_AGE_KEY_FILE"]).expanduser().resolve()
    if key.is_relative_to(ROOT):
        raise ValueError("Store the private age key outside the project")
    secure_directory(key.parent)
    if not key.exists():
        captured(["age-keygen", "-o", str(key)])
    if sys.platform != "win32":
        key.chmod(0o600)
    recipient = captured(["age-keygen", "-y", str(key)]).decode().strip()
    values.update(make_pki())
    validate(values)
    ciphertext = captured(["sops", "encrypt", "--age", recipient, "--input-type", "json",
                           "--output-type", "json", "--filename-override", str(ENCRYPTED)],
                          data=json.dumps(values).encode())
    ENCRYPTED.parent.mkdir(parents=True, exist_ok=True)
    with ENCRYPTED.open("xb") as output:
        output.write(ciphertext)
    (ROOT / "config/ca.crt").write_text(values["TLS_CA_CERT"], encoding="ascii")
    # The creation rule contains only the public recipient, never the private key.
    rule = ROOT / ".sops.yaml"
    if not rule.exists():
        rule.write_text('creation_rules:\n  - path_regex: secrets\\.enc\\.json$\n'
                        f'    age: "{recipient}"\n', encoding="ascii")
    print("Created config/secrets.enc.json and public config/ca.crt. Back up your private age key separately.")
    if import_env:
        print("Imported existing credentials. The old .env still exists: archive it securely after verification.")


def decrypt(*, allow_recovery=True):
    # An already-open terminal may contain an empty, quoted or stale override.
    # Try that identity first, then the standard identity created by init. SOPS
    # itself verifies that an identity matches and checks the encrypted MAC.
    configured = os.environ.get("SOPS_AGE_KEY_FILE", "").strip().strip('"')
    candidates = []
    if configured:
        candidates.append(Path(os.path.expandvars(configured)).expanduser())
    candidates.append(default_age_key())
    attempted = set()
    readable = False
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in attempted:
            continue
        attempted.add(candidate)
        try:
            # Check actual access rather than just whether the path exists.
            with candidate.open("rb"):
                pass
        except OSError:
            continue
        readable = True
        env = dict(os.environ, SOPS_AGE_KEY_FILE=str(candidate))
        try:
            plaintext = captured(["sops", "decrypt", "--output-type", "json", str(ENCRYPTED)], env=env)
        except RuntimeError:
            continue
        values = json.loads(plaintext)
        validate(values)
        # Related commands (encrypted backups, age-keygen) need the same identity.
        os.environ["SOPS_AGE_KEY_FILE"] = str(candidate)
        return values
    if not readable:
        if allow_recovery and restore_age_key():
            return decrypt(allow_recovery=False)
        raise RuntimeError(
            "Cannot read the age private key. Run as the Windows user that initialized the project; "
            f"expected key: {default_age_key()}. Check SOPS_AGE_KEY_FILE and Windows permissions. "
            "Do not run init again or delete the encrypted configuration."
        )
    raise RuntimeError(
        "SOPS could not decrypt with the available age keys. Check that the key belongs to this "
        "project and that config/secrets.enc.json has not changed. The existing secrets were kept."
    )


def runtime_path():
    suffix = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
    if sys.platform == "win32":
        return ROOT / "secrets" / f"runtime-{suffix}"
    return Path(f"/dev/shm/cnc-guard-{os.getuid()}-{suffix}")


def materialize(values, runtime):
    secure_directory(runtime)

    def write(relative, text):
        path = runtime / relative
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if path.parent != runtime and sys.platform != "win32":
            path.parent.chmod(0o755)
        if path.is_symlink():
            raise ValueError("Runtime files cannot be symlinks")
        if path.exists() and sys.platform != "win32":
            path.chmod(0o600)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
        # Host traversal is blocked by runtime's 0700; bind mounts must be readable
        # by the different non-root UIDs inside the service containers.
        if sys.platform != "win32":
            path.chmod(0o444)

    write("ca.crt", values["TLS_CA_CERT"])
    for service in ("elasticsearch", "kibana", "scoring"):
        write(f"{service}/server.key", values[f"TLS_{service.upper()}_KEY"])
        write(f"{service}/server.crt", values[f"TLS_{service.upper()}_CERT"])
        write(f"{service}/ca.crt", values["TLS_CA_CERT"])
    for name in ("elastic_password", "mongo_password", "scoring_api_token"):
        write(name, values[name.upper()])
    if values.get("NIFI_KEYSTORE_P12"):
        write("nifi/keystore.p12", base64.b64decode(values["NIFI_KEYSTORE_P12"], validate=True))
    tls = "/usr/share/kibana/config/tls"
    kibana = {
        "server.host": "0.0.0.0", "server.name": "cnc-kibana",
        "server.ssl.enabled": True, "server.ssl.certificate": f"{tls}/server.crt",
        "server.ssl.key": f"{tls}/server.key",
        "elasticsearch.hosts": ["https://elasticsearch:9200"],
        "elasticsearch.ssl.certificateAuthorities": [f"{tls}/ca.crt"],
        "elasticsearch.ssl.verificationMode": "full",
        "elasticsearch.username": "kibana_system",
        "elasticsearch.password": values["KIBANA_SYSTEM_PASSWORD"],
        "xpack.security.encryptionKey": values["KIBANA_SECURITY_KEY"],
        "xpack.encryptedSavedObjects.encryptionKey": values["KIBANA_SAVED_OBJECTS_KEY"],
        "xpack.reporting.encryptionKey": values["KIBANA_REPORTING_KEY"],
        "xpack.security.secureCookies": True,
    }
    lan = lan_settings()
    if lan:
        kibana["server.publicBaseUrl"] = f"https://{lan['ip']}:5601"
    # JSON is a YAML subset, and escaping passwords is handled by json.dumps.
    write("kibana.yml", json.dumps(kibana, indent=2))


def lan_settings():
    path = ROOT / "config/lan.json"
    if not path.is_file():
        return None
    lan = json.loads(path.read_text(encoding="utf-8"))
    address = ipaddress.IPv4Address(lan["ip"])
    network = ipaddress.IPv4Network(lan["subnet"], strict=True)
    if address not in network or address.is_loopback or not address.is_private:
        raise ValueError("LAN settings must select a private IPv4 address in the configured subnet")
    return {"ip": str(address), "subnet": str(network)}


def compose(values, runtime, args):
    env = os.environ.copy()
    # Only legacy NiFi entrypoint and CIFS still require environment interpolation.
    for name in ("NIFI_USERNAME", "NIFI_PASSWORD", "MONGO_USERNAME", "SMB_USERNAME", "SMB_PASSWORD"):
        env[name] = values[name]
    env["CNC_RUNTIME_DIR"] = runtime.as_posix()
    empty_env = runtime / "compose.empty.env"
    empty_env.write_text("", encoding="ascii")
    files = ["-f", str(ROOT / "docker-compose.yml")]
    lan = lan_settings()
    if lan:
        env["CNC_LAN_IP"] = lan["ip"]
        files.extend(["-f", str(ROOT / "docker-compose.lan.yml")])
    subprocess.run(["docker", "compose", "--project-directory", str(ROOT), "--env-file",
                    str(empty_env), *files, *args],
                   env=env, cwd=ROOT, check=True)


def elastic_accounts(values, runtime):
    context = ssl.create_default_context(cafile=str(runtime / "ca.crt"))
    auth = base64.b64encode(f"elastic:{values['ELASTIC_PASSWORD']}".encode()).decode()
    # Ignore host proxy settings: this connection must remain on loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPSHandler(context=context))

    def request(path, body=None):
        req = urllib.request.Request("https://localhost:9200" + path,
              data=json.dumps(body).encode() if body is not None else None,
              headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
        try:
            with opener.open(req, timeout=5) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise RuntimeError("Elastic rejected ELASTIC_PASSWORD; an existing secured volume needs password recovery (see SECURITY.md)") from None
            raise RuntimeError(f"Elasticsearch security request failed with HTTP {error.code}") from None

    for attempt in range(90):
        try:
            request("/_security/_authenticate")
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 89:
                raise RuntimeError("Elasticsearch did not become ready; inspect its logs") from None
            time.sleep(2)
    request("/_security/user/kibana_system/_password", {"password": values["KIBANA_SYSTEM_PASSWORD"]})
    request("/_security/role/cnc_ingest", {
        "cluster": ["monitor"],
        "indices": [{"names": ["cnc-*"], "privileges": ["auto_configure", "create_index", "write", "view_index_metadata"]}],
    })
    request("/_security/user/cnc_nifi", {"password": values["NIFI_ELASTIC_PASSWORD"], "roles": ["cnc_ingest"]})
    request("/_security/role/cnc_dashboard", {
        "cluster": ["monitor"],
        "indices": [{"names": ["cnc-*"], "privileges": ["read", "view_index_metadata"]}],
        "applications": [{"application": "kibana-.kibana", "privileges": ["read"], "resources": ["space:default"]}],
    })
    request(f"/_security/user/{values['KIBANA_USERNAME']}", {
        "password": values["KIBANA_PASSWORD"], "roles": ["cnc_dashboard"],
    })
    print("Configured kibana_system, cnc_nifi and the Kibana read-only user (cnc-*).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="Generate the encrypted configuration once, on this computer")
    initialize.add_argument("--import-env", metavar="PATH")
    commands.add_parser("up", help="Prepare private runtime files, start ES, provision accounts, then start services")
    commands.add_parser("down", help="Stop containers without deleting data volumes, then clear runtime files")
    show = commands.add_parser("show", help="Reveal one value locally for NiFi or login setup")
    show.add_argument("name", choices=REQUIRED)
    compose_parser = commands.add_parser("compose", help="Run a Compose command using the encrypted configuration")
    compose_parser.add_argument("args", nargs=argparse.REMAINDER)
    commands.add_parser("doctor", help="Report process identity and key access errors without displaying secrets")
    args = parser.parse_args()
    if args.command == "doctor":
        doctor()
        return
    if sys.platform not in ("linux", "win32"):
        parser.error("Supported hosts: Windows with Docker Desktop, or Linux")
    if sys.platform == "linux" and not Path("/dev/shm").is_dir():
        parser.error("Linux runtime requires /dev/shm")
    os.umask(0o077)
    if not os.environ.get("SOPS_AGE_KEY_FILE", "").strip():
        os.environ["SOPS_AGE_KEY_FILE"] = str(default_age_key())
    if args.command == "init":
        init(args.import_env)
        return
    values = decrypt()
    if args.command == "show":
        print(values[args.name])
        return
    runtime = runtime_path()
    materialize(values, runtime)
    if args.command == "up":
        compose(values, runtime, ["up", "-d", "elasticsearch"])
        elastic_accounts(values, runtime)
        compose(values, runtime, ["up", "-d", "--build", "--force-recreate"])
    elif args.command == "down":
        compose(values, runtime, ["down"])
        shutil.rmtree(runtime)
    else:
        if not args.args:
            parser.error("Provide a Compose command, such as ps or logs")
        compose(values, runtime, args.args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        # Deliberately avoid traceback, environment dumps or decrypted payloads.
        print(f"Security setup failed: {error}", file=sys.stderr)
        sys.exit(1)
