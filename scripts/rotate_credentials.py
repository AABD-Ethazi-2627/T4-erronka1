"""Rotate the live NiFi and MongoDB accounts, without printing passwords.

New passwords are generated locally. Encrypted old/new vault copies are kept
under secrets/rotations to permit recovery if the operation is interrupted.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security, configure_nifi


def validate_username(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}", name):
        raise ValueError("Use a username of 3-64 letters, digits, underscores, dots or hyphens")


def clean_mongo_uri(uri):
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme not in ("mongodb", "mongodb+srv") or not parsed.netloc:
        raise ValueError("Expected a MongoDB connection URI")
    parameters = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    parameters = [(key, value) for key, value in parameters if key.lower() not in ("authsource", "authmechanism")]
    parameters.append(("authSource", "admin"))
    # Authentication belongs in the sensitive controller properties, not the URI.
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1],
                                   parsed.path, urllib.parse.urlencode(parameters), parsed.fragment))


MONGO_SCRIPT = r'''
const c=JSON.parse(require("fs").readFileSync(0,"utf8"));
const a=db.getSiblingDB("admin");
let authenticated=false;
try { authenticated=!!a.auth({user:c.user,pwd:c.password}); } catch(e) {}
if(c.action==="checkAuth") { print(JSON.stringify({authenticated})); }
else {
  if(!authenticated) throw new Error("MongoDB authentication failed");
  if(c.action==="preflight") {
    if(c.target===c.user) throw new Error("Choose a new MongoDB username");
    if(a.getUser(c.target)!==null) throw new Error("Target MongoDB user already exists");
    print(JSON.stringify({ok:true}));
  } else if(c.action==="create") {
    if(a.getUser(c.target)!==null) throw new Error("Target MongoDB user already exists");
    const original=a.getUser(c.user);
    const created=a.runCommand({createUser:c.target,pwd:c.newPassword,roles:original.roles,customData:original.customData || {}});
    if(created.ok!==1) throw new Error("Creating the new MongoDB account failed");
    print(JSON.stringify({ok:true}));
  } else if(c.action==="retire") {
    if(c.target===c.user) throw new Error("Refusing to remove the active account");
    if(a.getUser(c.target)!==null) {
      const removed=a.runCommand({dropUser:c.target});
      if(removed.ok!==1) throw new Error("Retiring the previous MongoDB account failed");
    }
    print(JSON.stringify({oldAccountRemoved:a.getUser(c.target)===null}));
  } else if(c.action==="probe") {
    const own=a.getUser(c.user);
    print(JSON.stringify({authenticated:true,roles:own.roles.map(r=>r.role)}));
  }
}
'''


def mongo(user, password, action, **extra):
    raw = security.captured(["docker", "exec", "-i", "cnc-mongodb", "mongosh", "--quiet", "--eval", MONGO_SCRIPT],
                            data=json.dumps({"user": user, "password": password, "action": action, **extra}).encode())
    # Tools and credentials are captured; only explicit non-sensitive checks are printed.
    return json.loads(raw)


def seal(values, destination):
    recipient = security.captured(["age-keygen", "-y", os.environ["SOPS_AGE_KEY_FILE"]]).decode().strip()
    ciphertext = security.captured(["sops", "encrypt", "--age", recipient, "--input-type", "json",
                                   "--output-type", "json", "--filename-override", str(security.ENCRYPTED)],
                                  data=json.dumps(values).encode())
    with destination.open("xb") as output:
        output.write(ciphertext)
    recovered = json.loads(security.captured(["sops", "decrypt", "--output-type", "json", str(destination)]))
    if recovered != values:
        raise RuntimeError("Encrypted credential staging verification failed")
    return ciphertext


def nifi_login_accepted(values):
    context = ssl.create_default_context(cafile=str(security.ROOT / "config/ca.crt"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request("https://localhost:8443/nifi-api/access/token",
        data=urllib.parse.urlencode({"username": values["NIFI_USERNAME"], "password": values["NIFI_PASSWORD"]}).encode())
    try:
        with opener.open(request, timeout=15) as response:
            response.read()  # Never display or persist the session token.
            return response.status == 201
    except urllib.error.HTTPError as error:
        if error.code in (400, 401, 403):
            return False
        raise RuntimeError(f"NiFi login verification returned HTTP {error.code}") from None


def rotate(nifi_username, mongo_username):
    validate_username(nifi_username)
    validate_username(mongo_username)
    old = security.decrypt()
    if nifi_username == old["NIFI_USERNAME"] and mongo_username == old["MONGO_USERNAME"]:
        raise ValueError("Both accounts already have these usernames; this operation expects new usernames")
    original = security.ENCRYPTED.read_bytes()
    folder = security.ROOT / "secrets/rotations"
    security.secure_directory(folder)
    journal = folder / "active.json"
    if journal.exists():
        raise RuntimeError("An interrupted rotation exists in secrets/rotations/active.json; recover it before starting another")
    # Collision and current-credential checks happen before any modification.
    mongo(old["MONGO_USERNAME"], old["MONGO_PASSWORD"], "preflight", target=mongo_username)
    api = configure_nifi.NiFi(old)
    _, _, services = api.inventory()
    mongo_services = [service for service in services.values()
                      if service["component"]["type"].endswith("MongoDBControllerService")]
    if not mongo_services:
        raise RuntimeError("No NiFi MongoDB controller service was found")
    for service in mongo_services:
        props = service["component"].get("properties", {})
        clean_mongo_uri(props.get("mongo-uri") or "")
    new = dict(old)
    new.update(NIFI_USERNAME=nifi_username, NIFI_PASSWORD=secrets.token_urlsafe(36),
               MONGO_USERNAME=mongo_username, MONGO_PASSWORD=secrets.token_urlsafe(36))
    security.validate(new)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = folder / f"before-{stamp}.enc.json"
    staged = folder / f"after-{stamp}.enc.json"
    backup.write_bytes(original)
    ciphertext = seal(new, staged)
    record = {"oldVault": backup.name, "newVault": staged.name, "phase": "prepared"}

    def phase(name):
        record["phase"] = name
        journal.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("Rotation: " + name, flush=True)

    phase("prepared")
    mongo(old["MONGO_USERNAME"], old["MONGO_PASSWORD"], "create",
          target=mongo_username, newPassword=new["MONGO_PASSWORD"])
    if not mongo(new["MONGO_USERNAME"], new["MONGO_PASSWORD"], "probe")["authenticated"]:
        raise RuntimeError("The new MongoDB account could not authenticate")
    phase("new-mongodb-account-verified")
    configure_nifi.pause(api)
    for service in mongo_services:
        sid = service["id"]
        configure_nifi.NiFi.service_state(api, sid, "DISABLED")
        entity = api.call("/controller-services/" + sid)
        uri = clean_mongo_uri(entity["component"]["properties"]["mongo-uri"])
        api.call("/controller-services/" + sid, {"revision": entity["revision"], "component": {
            "id": sid, "properties": {"mongo-uri": uri, "Database User": new["MONGO_USERNAME"],
                                       "Password": new["MONGO_PASSWORD"]}}}, "PUT")
        api.service_state(sid, "ENABLED")
    phase("nifi-mongodb-connection-updated")
    if security.ENCRYPTED.read_bytes() != original:
        raise RuntimeError("The vault changed concurrently; the old MongoDB account remains available")
    temporary = security.ENCRYPTED.with_suffix(".rotation.tmp")
    temporary.write_bytes(ciphertext)
    temporary.replace(security.ENCRYPTED)
    runtime = security.runtime_path()
    security.materialize(new, runtime)
    phase("vault-committed")
    # Official start.sh invokes set-single-user-credentials from these values.
    security.compose(new, runtime, ["up", "-d", "--force-recreate", "--no-deps", "mongodb", "nifi"])
    phase("services-recreated")
    api = configure_nifi.NiFi(new)
    if not nifi_login_accepted(new) or nifi_login_accepted(old):
        raise RuntimeError("NiFi credential replacement verification failed")
    if not mongo(new["MONGO_USERNAME"], new["MONGO_PASSWORD"], "probe")["authenticated"]:
        raise RuntimeError("MongoDB new credentials failed after restart")
    _, _, current_services = api.inventory()
    for service in mongo_services:
        component = current_services[service["id"]]["component"]
        props = component["properties"]
        entity = api.call("/controller-services/" + service["id"])["component"]
        parsed = urllib.parse.urlsplit(props["mongo-uri"])
        if (props.get("Database User") != mongo_username or parsed.username is not None or parsed.password is not None
                or not entity["descriptors"]["Password"]["sensitive"] or component["state"] != "ENABLED"):
            raise RuntimeError("NiFi MongoDB credential protection verification failed")
    phase("new-credentials-verified")
    configure_nifi.resume(api)
    for attempt in range(30):
        _, processors, _ = api.inventory()
        if any(p["component"].get("validationStatus") == "INVALID" for p in processors.values()):
            raise RuntimeError("A NiFi processor is invalid after rotation; the old MongoDB account has been kept")
        if all(p["component"].get("state") == "RUNNING" for p in processors.values()):
            break
        time.sleep(1)
    else:
        raise RuntimeError("NiFi flow did not fully resume; old MongoDB account kept")
    phase("nifi-flow-resumed")
    removed = mongo(new["MONGO_USERNAME"], new["MONGO_PASSWORD"], "retire", target=old["MONGO_USERNAME"])
    if not removed["oldAccountRemoved"] or mongo(old["MONGO_USERNAME"], old["MONGO_PASSWORD"], "checkAuth")["authenticated"]:
        raise RuntimeError("Old MongoDB account retirement could not be verified")
    phase("completed")
    journal.replace(folder / f"completed-{stamp}.json")
    print(f"Verified: NiFi and MongoDB now use {nifi_username} / {mongo_username}; old logins rejected; {len(processors)} valid running processors. Passwords stored only in SOPS.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nifi-user", required=True)
    parser.add_argument("--mongo-user", required=True)
    args = parser.parse_args()
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    rotate(args.nifi_user, args.mongo_user)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f"Credential rotation stopped: {error}. Encrypted recovery copies, if prepared, remain in secrets/rotations.", file=sys.stderr)
        sys.exit(1)
