"""Check Desktop bind mounts with private Windows ACLs; dummy secrets only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def main():
    if sys.platform != "win32":
        raise SystemExit("Run this check from Windows with Docker Desktop")
    values = {name: "dummy-test-value-" + "x" * 40 for name in security.REQUIRED}
    values.update(security.make_pki())
    with tempfile.TemporaryDirectory(prefix="docker-check-", dir=security.ROOT / ".venv") as temporary:
        runtime = Path(temporary) / "runtime"
        security.materialize(values, runtime)
        check = (
            "import ssl; from pathlib import Path; "
            "ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain('/run/tls/server.crt', '/run/tls/server.key'); "
            "assert Path('/run/secrets/scoring_api_token').read_text().startswith('dummy-test-value-'); "
            "print('PASS: Docker Desktop reads the token and TLS key through readonly Windows bind mounts')"
        )
        subprocess.run([
            "docker", "run", "--rm", "--user", "1000:1000", "--network", "none",
            "--mount", f"type=bind,source={runtime / 'scoring'},target=/run/tls,readonly",
            "--mount", f"type=bind,source={runtime / 'scoring_api_token'},target=/run/secrets/scoring_api_token,readonly",
            "--entrypoint", "python", os.environ.get("CNC_TEST_IMAGE", "t4-erronka1-scoring-api:latest"),
            "-c", check,
        ], check=True)


if __name__ == "__main__":
    main()
