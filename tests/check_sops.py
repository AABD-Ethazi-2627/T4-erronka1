"""Real SOPS/age smoke check on Windows or Linux; temporary dummy secrets only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def main():
    os.umask(0o077)
    temp_base = "/dev/shm" if sys.platform == "linux" else None
    with tempfile.TemporaryDirectory(prefix="cnc-security-check-", dir=temp_base) as temporary:
        base = Path(temporary)
        project = base / "project"
        project.mkdir()
        original = project / ".env"
        original.write_text("NIFI_USERNAME=testadmin\nNIFI_PASSWORD=test-nifi-password-not-real\n"
                            "MONGO_USERNAME=testmongo\nMONGO_PASSWORD=test-mongo-password-not-real\n"
                            "SMB_USERNAME=test-smb\nSMB_PASSWORD='test-smb$not-real'\n")
        encrypted = project / "config/secrets.enc.json"
        with patch.object(security, "ROOT", project), patch.object(security, "ENCRYPTED", encrypted), \
             patch.dict(os.environ, {"SOPS_AGE_KEY_FILE": str(base / "key/keys.txt")}):
            security.init(str(original))
            values = security.decrypt()
            assert values["SMB_PASSWORD"] == "test-smb$not-real"
            assert values["MONGO_PASSWORD"] == "test-mongo-password-not-real"
            assert values["NIFI_PASSWORD"] == "test-nifi-password-not-real"
            assert "test-mongo-password-not-real" not in encrypted.read_text()
            assert "PRIVATE KEY" not in encrypted.read_text()
            assert "AGE-SECRET-KEY" not in (project / ".sops.yaml").read_text()
            recipient = security.captured(["age-keygen", "-y", str(base / "key/keys.txt")]).decode().strip()
            # The generated rule must match native Windows paths on later writes.
            security.captured(["sops", "encrypt", "--age", recipient, "--input-type", "binary",
                               "--output-type", "json", "--filename-override", str(encrypted)], data=b"dummy backup")
            runtime = base / "runtime"
            security.materialize(values, runtime)
            if sys.platform == "linux":
                assert runtime.stat().st_mode & 0o777 == 0o700
                assert (runtime / "scoring").stat().st_mode & 0o777 == 0o755
            assert not (runtime / "ca.key").exists()
            config = json.loads((runtime / "kibana.yml").read_text())
            assert config["elasticsearch.password"] == values["KIBANA_SYSTEM_PASSWORD"]
            for service, hostname in (("elasticsearch", "elasticsearch"),
                                      ("kibana", "localhost"), ("scoring", "scoring-api")):
                from cryptography import x509
                from cryptography.hazmat.primitives import serialization
                ca = x509.load_pem_x509_certificate((runtime / "ca.crt").read_bytes())
                cert = x509.load_pem_x509_certificate((runtime / service / "server.crt").read_bytes())
                cert.verify_directly_issued_by(ca)
                assert hostname in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
                key = serialization.load_pem_private_key((runtime / service / "server.key").read_bytes(), password=None)
                assert cert.public_key().public_numbers() == key.public_key().public_numbers()
            security.materialize(values, runtime)
            try:
                security.init(str(original))
            except ValueError:
                pass
            else:
                raise AssertionError("init must not overwrite encrypted secrets")
            # A different private identity cannot decrypt the file.
            wrong_key = base / "wrong.agekey"
            security.captured(["age-keygen", "-o", str(wrong_key)])
            with patch.dict(os.environ, {"SOPS_AGE_KEY_FILE": str(wrong_key)}):
                try:
                    security.decrypt()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("A different age identity must not decrypt the file")
    print("PASS: real SOPS/age roundtrip, wrong-key rejection, imported passwords, TLS trust/key matching and runtime permissions")


if __name__ == "__main__":
    main()
