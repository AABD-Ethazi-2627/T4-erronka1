"""Verify live authentication locally without printing secrets or predictions."""
import argparse
import base64
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", type=int, default=0)
    args = parser.parse_args()
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    values = security.decrypt()
    context = ssl.create_default_context(cafile=str(security.ROOT / "config/ca.crt"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))

    def check(label, url, expected, *, headers=None, data=None):
        request = urllib.request.Request(url, headers=headers or {},
                                         data=json.dumps(data).encode() if data is not None else None)
        try:
            with opener.open(request, timeout=15) as response:
                status = response.status
                body = response.read()
        except urllib.error.HTTPError as error:
            status, body = error.code, b""
        if status != expected:
            raise RuntimeError(f"{label}: expected HTTP {expected}, got {status}")
        print(f"PASS {label}: HTTP {status}")
        return body

    check("Elasticsearch requires authentication", "https://localhost:9200/", 401)
    basic = base64.b64encode(f"{values['KIBANA_USERNAME']}:{values['KIBANA_PASSWORD']}".encode()).decode()
    check("Kibana user can open Elasticsearch root", "https://localhost:9200/", 200,
          headers={"Authorization": "Basic " + basic})
    check("Kibana user authenticates against Elasticsearch", "https://localhost:9200/_security/_authenticate", 200,
          headers={"Authorization": "Basic " + basic})
    check("API requires token", "https://localhost:8000/predict", 401,
          headers={"Content-Type": "application/json"}, data={})
    check("API rejects incorrect token", "https://localhost:8000/predict", 401,
          headers={"Content-Type": "application/json", "Authorization": "Bearer invalid"}, data={})
    payload = {"timestamp": "2026-11-09T12:00:00Z", "machine_id": "security-check", "machine_type": "M",
               "air_temp_K": 300, "process_temp_K": 310, "rpm": 1500, "torque_Nm": 40, "tool_wear_min": 10}
    check("API predicts with valid token", "https://localhost:8000/predict", 200,
          headers={"Content-Type": "application/json", "Authorization": "Bearer " + values["SCORING_API_TOKEN"]}, data=payload)
    import time
    for attempt in range(args.wait + 1):
        try:
            body = check("Kibana login page", "https://localhost:5601/login", 200)
            break
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt == args.wait:
                raise
            time.sleep(1)
    check("Kibana accepts username/password", "https://localhost:5601/internal/security/login", 200,
          headers={"Content-Type": "application/json", "kbn-xsrf": "security-check"},
          data={"providerType": "basic", "providerName": "basic", "currentURL": "https://localhost:5601/login",
                "params": {"username": values["KIBANA_USERNAME"], "password": values["KIBANA_PASSWORD"]}})
    from scripts.configure_nifi import NiFi
    api = NiFi(values)
    _, processors, services = api.inventory()
    protected = 0
    for processor in processors.values():
        component = processor["component"]
        if component["type"].endswith("InvokeHTTP"):
            config = api.call("/processors/" + component["id"])["component"]["config"]
            if config["properties"].get("HTTP URL") != "https://scoring-api:8000/predict":
                continue
            if not config.get("descriptors", {}).get("Authorization", {}).get("sensitive"):
                raise RuntimeError("NiFi Authorization property is not marked sensitive")
            returned = config["properties"].get("Authorization")
            # NiFi versions return either null or asterisks for sensitive values.
            if returned is not None and (not returned or set(returned) != {"*"}):
                raise RuntimeError("NiFi API exposes an Authorization property value")
            protected += 1
    if not protected:
        raise RuntimeError("No protected NiFi scoring call was found")
    print(f"PASS NiFi API token is sensitive and hidden ({protected} processor)")
    running = sum(p["component"].get("state") == "RUNNING" for p in processors.values())
    invalid = sum(p["component"].get("validationStatus") == "INVALID" for p in processors.values())
    if invalid:
        raise RuntimeError("NiFi has invalid processors")
    print(f"PASS NiFi flow: {running} running processors, {invalid} invalid")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, urllib.error.URLError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        sys.exit(1)
