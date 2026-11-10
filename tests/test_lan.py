import ipaddress
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import configure_lan, security


class LanTests(unittest.TestCase):
    def test_firewall_excludes_lan_and_loopback_but_blocks_other_networks(self):
        plan = configure_lan.firewall_plan("192.168.75.221", "192.168.75.0/24")
        blocks = [ipaddress.ip_network(value) for value in plan["blocked_remote_ranges"]]
        for address, blocked in (("192.168.75.1", False), ("192.168.75.250", False),
                                 ("127.0.0.1", False), ("192.168.74.1", True),
                                 ("192.168.76.1", True), ("10.0.0.1", True), ("8.8.8.8", True)):
            self.assertEqual(any(ipaddress.ip_address(address) in block for block in blocks), blocked, address)
        self.assertEqual(set(plan["ports"]), {5601, 8443, 9200, 8000})

    def test_reissued_certificate_preserves_key_and_ca_and_adds_ip(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        values = security.make_pki()
        ca = x509.load_pem_x509_certificate(values["TLS_CA_CERT"].encode())
        ca_key = serialization.load_pem_private_key(values["TLS_CA_KEY"].encode(), password=None)
        old = x509.load_pem_x509_certificate(values["TLS_KIBANA_CERT"].encode())
        cert = configure_lan.reissue_certificate(values["TLS_KIBANA_CERT"], ca, ca_key, "192.168.75.221")
        cert.verify_directly_issued_by(ca)
        self.assertEqual(cert.public_key().public_numbers(), old.public_key().public_numbers())
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        self.assertIn(ipaddress.ip_address("192.168.75.221"), names.get_values_for_type(x509.IPAddress))
        self.assertIn("localhost", names.get_values_for_type(x509.DNSName))
        self.assertIn("kibana", names.get_values_for_type(x509.DNSName))
        self.assertNotIn("nifi", names.get_values_for_type(x509.DNSName))

    def test_lan_override_is_only_loaded_when_configured(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            runtime = root / "runtime"
            runtime.mkdir()
            values = {name: "dummy" for name in ("NIFI_USERNAME", "NIFI_PASSWORD", "MONGO_USERNAME", "SMB_USERNAME", "SMB_PASSWORD")}
            with patch.object(security, "ROOT", root), patch("subprocess.run") as run:
                security.compose(values, runtime, ["ps"])
                self.assertNotIn(str(root / "docker-compose.lan.yml"), run.call_args.args[0])
                (root / "config/lan.json").write_text(json.dumps({"ip": "192.168.75.221", "subnet": "192.168.75.0/24"}))
                security.compose(values, runtime, ["ps"])
                self.assertIn(str(root / "docker-compose.lan.yml"), run.call_args.args[0])
                self.assertEqual(run.call_args.kwargs["env"]["CNC_LAN_IP"], "192.168.75.221")


if __name__ == "__main__":
    unittest.main()
