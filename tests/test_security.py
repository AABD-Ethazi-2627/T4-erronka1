"""Run with: python -m unittest discover -s tests -v."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from scoring import score_api
from scripts import security

TOKEN = "test-token-" + "a" * 40
PAYLOAD = {
    "timestamp": "2026-11-09T12:00:00Z", "machine_id": "cnc-01", "machine_type": "M",
    "air_temp_K": 300, "process_temp_K": 310, "rpm": 1500,
    "torque_Nm": 40, "tool_wear_min": 10,
}


class Model:
    classes_ = [0, 1]

    def predict_proba(self, features):
        return [[0.9, 0.1]]


class ApiAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.token_file = Path(self.folder.name) / "token"
        self.token_file.write_text(TOKEN)
        self.environment = patch.dict(os.environ, {"SCORING_API_TOKEN_FILE": str(self.token_file)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_invalid_credentials_are_rejected_before_inference(self):
        model = Model()
        with patch.object(score_api, "_load_model", return_value=model), TestClient(score_api.app) as client:
            for header in (None, "Bearer wrong", "Basic dXNlcjpwYXNz", "Bearer", "Bearer " + TOKEN[:-1]):
                headers = {"Authorization": header} if header else {}
                with self.subTest(header=header), patch.object(model, "predict_proba") as inference:
                    response = client.post("/predict", json=PAYLOAD, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    inference.assert_not_called()

    def test_authorized_request_still_predicts(self):
        with patch.object(score_api, "_load_model", return_value=Model()), TestClient(score_api.app) as client:
            response = client.post("/predict", json=PAYLOAD, headers={"Authorization": f"Bearer {TOKEN}"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["failure_probability"], 0.1)
            self.assertIn("HTTPBearer", client.get("/openapi.json").json()["components"]["securitySchemes"])

    def test_missing_or_short_token_prevents_startup(self):
        for content in (None, "", "short", "x" * 32 + "\ninside", "é" * 40):
            if content is None:
                self.token_file.unlink(missing_ok=True)
            else:
                self.token_file.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(RuntimeError):
                with TestClient(score_api.app):
                    pass

    def test_health_does_not_disclose_files_or_token(self):
        with patch.object(score_api, "_load_model", return_value=None), TestClient(score_api.app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("model_path", response.json())
            self.assertNotIn(TOKEN, response.text)
            self.assertEqual(client.post("/predict", json=PAYLOAD).status_code, 401)
            self.assertEqual(client.post("/predict", json=PAYLOAD,
                                        headers={"Authorization": f"Bearer {TOKEN}"}).status_code, 503)


def example_values():
    values = {name: "test-value-" + "x" * 40 for name in security.REQUIRED}
    values.update(KIBANA_USERNAME="cncviewer", SMB_USERNAME="smbuser")
    return values


class DeploymentTests(unittest.TestCase):
    def test_decrypt_recovers_from_stale_or_quoted_terminal_key_setting(self):
        values = example_values()
        with tempfile.TemporaryDirectory() as folder:
            identity = Path(folder) / "keys.txt"
            identity.write_text("dummy identity")
            for setting in ("", str(Path(folder) / "missing.txt"), '"' + str(identity) + '"'):
                with self.subTest(setting=setting), \
                     patch.dict(os.environ, {"SOPS_AGE_KEY_FILE": setting}), \
                     patch.object(security, "default_age_key", return_value=identity), \
                     patch.object(security, "captured", return_value=json.dumps(values).encode()) as decrypt:
                    self.assertEqual(security.decrypt(), values)
                    self.assertEqual(decrypt.call_args.kwargs["env"]["SOPS_AGE_KEY_FILE"], str(identity.resolve()))
                    self.assertEqual(os.environ["SOPS_AGE_KEY_FILE"], str(identity.resolve()))

    def test_decrypt_does_not_recreate_keys_or_files_if_identity_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "missing.txt"
            with patch.dict(os.environ, {"SOPS_AGE_KEY_FILE": ""}), \
                 patch.object(security, "default_age_key", return_value=missing), \
                 patch.object(security, "restore_age_key", return_value=False), \
                 patch.object(security, "captured") as tool:
                with self.assertRaisesRegex(RuntimeError, "Cannot read the age private key"):
                    security.decrypt()
                tool.assert_not_called()
                self.assertFalse(missing.exists())

    def test_legacy_import_preserves_literal_secrets_without_executing_them(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / ".env"
            source.write_text("# comment\nSMB_USERNAME=DOMAIN\\user\nSMB_PASSWORD='literal$pass # word'\nNIFI_PASSWORD=some-long-password # comment\n")
            values = security.read_legacy_env(source)
            self.assertEqual(values["SMB_USERNAME"], "DOMAIN\\user")
            self.assertEqual(values["SMB_PASSWORD"], "literal$pass # word")
            self.assertEqual(values["NIFI_PASSWORD"], "some-long-password")

    def test_unsafe_mount_options_and_interpolated_dotenv_are_rejected(self):
        values = example_values()
        values["SMB_PASSWORD"] = "pass,ro"
        with self.assertRaises(ValueError):
            security.validate(values)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / ".env"
            source.write_text("SMB_PASSWORD=${OTHER}\n")
            with self.assertRaises(ValueError):
                security.read_legacy_env(source)

    @unittest.skipUnless(os.name == "posix", "Linux file permissions and tmpfs")
    def test_runtime_is_private_and_service_keys_are_separated(self):
        values = example_values()
        values["KIBANA_SYSTEM_PASSWORD"] = 'quote"and\\slash' + "x" * 32
        with tempfile.TemporaryDirectory(dir="/dev/shm") as folder:
            runtime = Path(folder) / "runtime"
            security.materialize(values, runtime)
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o700)
            self.assertEqual((runtime / "elasticsearch").stat().st_mode & 0o777, 0o755)
            config = json.loads((runtime / "kibana.yml").read_text())
            self.assertEqual(config["elasticsearch.password"], values["KIBANA_SYSTEM_PASSWORD"])
            self.assertTrue(config["server.ssl.enabled"])
            self.assertEqual(config["elasticsearch.ssl.verificationMode"], "full")
            self.assertFalse((runtime / "ca.key").exists())
            self.assertEqual(sorted(p.name for p in (runtime / "scoring").iterdir()),
                             ["ca.crt", "server.crt", "server.key"])
            # Re-materialization must work despite the previous readonly files.
            security.materialize(values, runtime)

    def test_compose_ignores_plaintext_dotenv_and_minimizes_environment(self):
        values = example_values()
        with tempfile.TemporaryDirectory() as folder, patch("subprocess.run") as run:
            security.compose(values, Path(folder), ["ps"])
            self.assertEqual((Path(folder) / "compose.empty.env").read_text(), "")
        command = run.call_args.args[0]
        self.assertTrue(command[command.index("--env-file") + 1].endswith("compose.empty.env"))
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["NIFI_PASSWORD"], values["NIFI_PASSWORD"])
        self.assertNotIn("SCORING_API_TOKEN", env)
        self.assertNotIn("ELASTIC_PASSWORD", env)

    @unittest.skipUnless(os.name == "nt", "Windows ACL verification")
    def test_windows_runtime_acl_and_native_compose_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder) / "runtime"
            security.materialize(example_values(), runtime)
            self.assertEqual((runtime / "scoring_api_token").read_text(), example_values()["SCORING_API_TOKEN"])
            script = (
                "$acl = [System.IO.Directory]::GetAccessControl($env:CNC_TEST_DIRECTORY); "
                "$acl.AreAccessRulesProtected; "
                "$acl.Access | ForEach-Object { $_.IdentityReference.Translate("
                "[System.Security.Principal.SecurityIdentifier]).Value }"
            )
            acl = security.captured(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                    env=dict(os.environ, CNC_TEST_DIRECTORY=str(runtime))).decode()
            self.assertIn("True", acl)
            self.assertIn("S-1-5-18", acl)
            self.assertNotIn("S-1-1-0", acl)  # Everyone
            self.assertNotIn("S-1-5-32-545", acl)  # Users
            self.assertEqual(json.loads((runtime / "kibana.yml").read_text())["server.ssl.enabled"], True)

    def test_service_certificates_are_signed_by_ca_and_have_separate_keys(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        values = security.make_pki()
        ca = x509.load_pem_x509_certificate(values["TLS_CA_CERT"].encode())
        keys = set()
        for service, hostname in (("ELASTICSEARCH", "elasticsearch"), ("KIBANA", "kibana"), ("SCORING", "scoring-api")):
            cert = x509.load_pem_x509_certificate(values[f"TLS_{service}_CERT"].encode())
            cert.verify_directly_issued_by(ca)
            key = serialization.load_pem_private_key(values[f"TLS_{service}_KEY"].encode(), password=None)
            self.assertEqual(cert.public_key().public_numbers(), key.public_key().public_numbers())
            self.assertIn(hostname, cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName))
            keys.add(values[f"TLS_{service}_KEY"])
        self.assertEqual(len(keys), 3)


if __name__ == "__main__":
    unittest.main()
