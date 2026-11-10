"""Verify the four HTTPS endpoints over the configured server LAN IP."""
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def main():
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    values = security.decrypt()
    lan = security.lan_settings()
    if not lan:
        raise RuntimeError("LAN access has not been configured")
    host = lan["ip"]
    context = ssl.create_default_context(cafile=str(security.ROOT / "config/ca.crt"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
              urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def check(label, port, path, expected, data=None, headers=None, form=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        if form is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
            body = urllib.parse.urlencode(form).encode()
        else:
            body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(f"https://{host}:{port}{path}", data=body, headers=h)
        try:
            with opener.open(req, timeout=15) as response:
                status = response.status
                response.read()  # Never print login responses or prediction data.
        except urllib.error.HTTPError as error:
            status = error.code
        if status != expected:
            raise RuntimeError(f"{label}: expected HTTP {expected}, got {status}")
        print(f"PASS {label}: HTTPS {host}:{port}, certificate verified, HTTP {status}", flush=True)

    for attempt in range(90):
        try:
            check("Elasticsearch requires credentials", 9200, "/", 401)
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 89:
                raise
            time.sleep(2)
    basic = base64.b64encode(f"{values['KIBANA_USERNAME']}:{values['KIBANA_PASSWORD']}".encode()).decode()
    check("Elasticsearch viewer login", 9200, "/", 200, headers={"Authorization": "Basic " + basic})
    check("Scoring rejects unauthenticated requests", 8000, "/predict", 401, data={})
    payload = {"timestamp": "2026-11-09T12:00:00Z", "machine_id": "lan-check", "machine_type": "M",
               "air_temp_K": 300, "process_temp_K": 310, "rpm": 1500, "torque_Nm": 40, "tool_wear_min": 10}
    check("Scoring accepts valid token", 8000, "/predict", 200, data=payload,
          headers={"Authorization": "Bearer " + values["SCORING_API_TOKEN"]})
    for port, path, label in ((5601, "/login", "Kibana login page"), (8443, "/nifi/", "NiFi interface")):
        for attempt in range(90):
            try:
                check(label, port, path, 200)
                break
            except (urllib.error.URLError, TimeoutError, RuntimeError):
                if attempt == 89:
                    raise
                time.sleep(2)
    check("Kibana password login", 5601, "/internal/security/login", 200,
          headers={"kbn-xsrf": "lan-verification"}, data={"providerType": "basic", "providerName": "basic",
              "currentURL": f"https://{host}:5601/login", "params": {"username": values["KIBANA_USERNAME"], "password": values["KIBANA_PASSWORD"]}})
    check("Kibana dashboard read", 5601, "/api/saved_objects/_find?type=dashboard&per_page=1", 200)
    check("NiFi password login", 8443, "/nifi-api/access/token", 201,
          form={"username": values["NIFI_USERNAME"], "password": values["NIFI_PASSWORD"]})


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print(f"LAN verification failed: {error}", file=sys.stderr)
        sys.exit(1)
