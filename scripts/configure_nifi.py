"""Migrate the running local NiFi flow to HTTPS and sensitive credentials.

Never print API response bodies, credentials or decrypted configuration.
Commands: pause (encrypted backup), apply, resume, status.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security

STATE = security.ROOT / "secrets/nifi-migration-state.json"


class NiFi:
    def __init__(self, values):
        certificate = security.ROOT / ("config/ca.crt" if values.get("TLS_NIFI_CERT") else "config/nifi-server.crt")
        if not certificate.exists():
            raise RuntimeError("Missing pinned local NiFi certificate config/nifi-server.crt")
        context = ssl.create_default_context(cafile=str(certificate))
        # NiFi's pre-existing local certificate uses its container hostname.
        # The certificate itself is pinned; connections are loopback only.
        context.check_hostname = bool(values.get("TLS_NIFI_CERT"))
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                          urllib.request.HTTPSHandler(context=context))
        self.token = None
        form = urllib.parse.urlencode({"username": values["NIFI_USERNAME"],
                                      "password": values["NIFI_PASSWORD"]}).encode()
        request = urllib.request.Request("https://localhost:8443/nifi-api/access/token", data=form)
        for attempt in range(90):
            try:
                with self.opener.open(request, timeout=10) as response:
                    self.token = response.read().decode()
                break
            except urllib.error.HTTPError as error:
                if error.code in (400, 401, 403):
                    raise RuntimeError("NiFi rejected the configured login credentials") from None
                if attempt == 89:
                    raise RuntimeError(f"NiFi login endpoint returned HTTP {error.code}") from None
                time.sleep(2)
            except (urllib.error.URLError, TimeoutError):
                if attempt == 89:
                    raise RuntimeError("NiFi is not ready for authenticated access") from None
                time.sleep(2)

    def call(self, path, data=None, method=None):
        request = urllib.request.Request("https://localhost:8443/nifi-api" + path,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
                  method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"NiFi HTTP {error.code} on {path.split('?')[0]}") from None

    def inventory(self):
        groups, processors, services = [], {}, {}
        pending = ["root"]
        while pending:
            group = self.call("/flow/process-groups/" + pending.pop())["processGroupFlow"]
            gid, flow = group["id"], group["flow"]
            groups.append(gid)
            processors.update({p["id"]: p for p in flow.get("processors", [])})
            for service in self.call(f"/flow/process-groups/{gid}/controller-services").get("controllerServices", []):
                services[service["id"]] = service
            pending.extend(g["id"] for g in flow.get("processGroups", []))
        return groups, processors, services

    def service_state(self, sid, state):
        current = self.call("/controller-services/" + sid)
        if current["component"]["state"] == state:
            return
        self.call(f"/controller-services/{sid}/run-status", {"revision": current["revision"], "state": state}, "PUT")
        for _ in range(60):
            if self.call("/controller-services/" + sid)["component"]["state"] == state:
                return
            time.sleep(1)
        raise RuntimeError(f"NiFi controller service did not reach {state}")


def pause(api):
    groups, processors, _ = api.inventory()
    if STATE.exists():
        print("Existing migration state preserved; flow is already prepared for migration.")
        return
    backups = security.ROOT / "secrets/backups"
    security.secure_directory(backups)
    archive = security.captured(["docker", "exec", "cnc-nifi", "tar", "-czf", "-", "-C", "/opt/nifi/nifi-current", "conf"])
    recipient = security.captured(["age-keygen", "-y", os.environ["SOPS_AGE_KEY_FILE"]]).decode().strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"nifi-before-security-{stamp}.enc.json"
    encrypted = security.captured(["sops", "encrypt", "--age", recipient, "--input-type", "binary",
                                  "--output-type", "json", "--filename-override", str(security.ENCRYPTED)], data=archive)
    backup.write_bytes(encrypted)
    state = {"root": groups[0], "running": [pid for pid, p in processors.items() if p["component"].get("state") == "RUNNING"]}
    STATE.write_text(json.dumps(state), encoding="utf-8")
    api.call("/flow/process-groups/" + groups[0], {"id": groups[0], "state": "STOPPED"}, "PUT")
    for _ in range(60):
        _, current, _ = api.inventory()
        if all(p["component"].get("state") != "RUNNING" and
               p.get("status", {}).get("aggregateSnapshot", {}).get("activeThreadCount", 0) == 0 for p in current.values()):
            print(f"Encrypted NiFi configuration backup saved; paused {len(state['running'])} running processors.")
            return
        time.sleep(1)
    raise RuntimeError("NiFi processors are still stopping; do not restart Docker yet")


def apply(api, values):
    _, processors, services = api.inventory()
    if any(p["component"].get("state") == "RUNNING" for p in processors.values()):
        raise RuntimeError("Run pause before changing NiFi connections")
    truststore = "/opt/nifi/nifi-current/conf/cnc-truststore.p12"
    check = subprocess.run(["docker", "exec", "cnc-nifi", "keytool", "-list", "-alias", "cnc-guard-ca",
                            "-keystore", truststore, "-storetype", "PKCS12", "-storepass", "changeit"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check.returncode:
        security.captured(["docker", "exec", "cnc-nifi", "keytool", "-importcert", "-noprompt", "-alias", "cnc-guard-ca",
                           "-file", "/opt/nifi/security/ca.crt", "-keystore", truststore, "-storetype", "PKCS12", "-storepass", "changeit"])
    elastic = [s for s in services.values() if s["component"]["type"].endswith("ElasticSearchClientServiceImpl")]
    http = [p for p in processors.values() if p["component"]["type"].endswith("InvokeHTTP")]
    if not elastic or not http:
        raise RuntimeError("Expected Elasticsearch client and InvokeHTTP were not found")
    for service in elastic:
        api.service_state(service["id"], "DISABLED")
    parent = elastic[0]["component"]["parentGroupId"]
    existing = next((s for s in services.values() if s["component"]["name"] == "CNC TLS Trust"), None)
    if existing:
        sid = existing["id"]
        api.service_state(sid, "DISABLED")
    else:
        types = api.call("/flow/controller-service-types?type=org.apache.nifi.ssl.StandardSSLContextService")
        descriptor = next(d for d in types["controllerServiceTypes"] if d["type"] == "org.apache.nifi.ssl.StandardSSLContextService")
        entity = api.call(f"/process-groups/{parent}/controller-services", {
            "revision": {"version": 0}, "component": {"name": "CNC TLS Trust", "type": descriptor["type"], "bundle": descriptor["bundle"]}})
        sid = entity["id"]
    entity = api.call("/controller-services/" + sid)
    props = {"Truststore Filename": truststore, "Truststore Type": "PKCS12", "Truststore Password": "changeit"}
    descriptors = entity["component"].get("descriptors", {})
    mapped = {}
    for label, value in props.items():
        key = next((name for name, d in descriptors.items() if d.get("displayName") == label or name == label), None)
        if key is None:
            raise RuntimeError(f"NiFi SSL property is unavailable: {label}")
        mapped[key] = value
    api.call("/controller-services/" + sid, {"revision": entity["revision"], "component": {"id": sid, "properties": mapped}}, "PUT")
    api.service_state(sid, "ENABLED")
    for service in elastic:
        eid = service["id"]
        entity = api.call("/controller-services/" + eid)
        auth = entity["component"].get("descriptors", {}).get("authorization-scheme", {}).get("allowableValues", [])
        basic = next((v["allowableValue"]["value"] for v in auth if "basic" in str(v).lower()), "BASIC")
        props = {"el-cs-http-hosts": "https://elasticsearch:9200", "el-cs-username": "cnc_nifi",
                 "el-cs-password": values["NIFI_ELASTIC_PASSWORD"], "el-cs-ssl-context-service": sid,
                 "el-cs-sniff-cluster-nodes": "false", "authorization-scheme": basic}
        api.call("/controller-services/" + eid, {"revision": entity["revision"], "component": {"id": eid, "properties": props}}, "PUT")
        api.service_state(eid, "ENABLED")
    for processor in http:
        pid = processor["id"]
        entity = api.call("/processors/" + pid)
        current_url = entity["component"]["config"]["properties"].get("HTTP URL", "")
        if urllib.parse.urlparse(current_url).hostname not in ("scoring-api", "localhost", "127.0.0.1"):
            continue
        sensitive = set(entity["component"]["config"].get("sensitiveDynamicPropertyNames", []))
        sensitive.add("Authorization")
        props = {"HTTP URL": "https://scoring-api:8000/predict", "SSL Context Service": sid,
                 "Authorization": "Bearer " + values["SCORING_API_TOKEN"]}
        api.call("/processors/" + pid, {"revision": entity["revision"], "component": {"id": pid,
                 "config": {"properties": props, "sensitiveDynamicPropertyNames": sorted(sensitive)}}}, "PUT")
    print(f"Configured NiFi TLS trust, {len(elastic)} Elasticsearch client(s), and sensitive API authentication.")


def resume(api):
    state = json.loads(STATE.read_text())
    _, processors, _ = api.inventory()
    for pid in state["running"]:
        if processors[pid]["component"].get("validationStatus") == "INVALID":
            raise RuntimeError(f"NiFi processor {pid} is invalid; migration remains paused")
    if set(state["running"]) == set(processors):
        api.call("/flow/process-groups/" + state["root"], {"id": state["root"], "state": "RUNNING"}, "PUT")
        STATE.replace(STATE.with_name("nifi-last-migration.json"))
        print(f"Resumed all {len(processors)} previously running processors.")
        return
    for pid in state["running"]:
        entity = api.call("/processors/" + pid)
        if entity["component"].get("validationStatus") == "INVALID":
            raise RuntimeError(f"NiFi processor {pid} is invalid; migration remains paused")
    for pid in state["running"]:
        entity = api.call("/processors/" + pid)
        api.call(f"/processors/{pid}/run-status", {"revision": entity["revision"], "state": "RUNNING"}, "PUT")
    STATE.replace(STATE.with_name("nifi-last-migration.json"))
    print(f"Resumed {len(state['running'])} processors that were running before migration.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pause", "apply", "resume", "status"))
    args = parser.parse_args()
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    values = security.decrypt()
    api = NiFi(values)
    if args.command == "pause":
        pause(api)
    elif args.command == "apply":
        apply(api, values)
    elif args.command == "resume":
        resume(api)
    else:
        groups, processors, services = api.inventory()
        print(json.dumps({"groups": len(groups), "processors": len(processors),
              "running": sum(p["component"].get("state") == "RUNNING" for p in processors.values()),
              "invalid": sum(p["component"].get("validationStatus") == "INVALID" for p in processors.values()),
              "servicesEnabled": sum(s["component"].get("state") == "ENABLED" for s in services.values())}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
