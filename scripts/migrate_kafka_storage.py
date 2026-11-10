"""One-time stopped-broker migration from /tmp/kafka-logs to the named volume.

Does not format Kafka storage or remove volumes. Keeps an encrypted recovery
archive and compares topic/consumer offsets before and after recreation.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security, configure_nifi

SOURCE = "/tmp/kafka-logs"
TARGET = "/var/lib/kafka/data"


def docker(*args, data=None):
    return security.captured(["docker", *args], data=data)


def inspect(name):
    return json.loads(docker("inspect", name))[0]


def kafka(tool, *args):
    return docker("exec", "cnc-kafka", "/opt/kafka/bin/" + tool,
                  "--bootstrap-server", "localhost:9092", *args).decode()


def storage_settings():
    text = kafka("kafka-configs.sh", "--entity-type", "brokers", "--entity-name", "1", "--describe", "--all")
    settings = {}
    for line in text.splitlines():
        match = re.match(r"\s*(log\.dirs|log\.dir|metadata\.log\.dir)=(.*?)\s+sensitive=", line)
        if match:
            settings[match[1]] = match[2]
    path = settings.get("log.dirs")
    if not path or path == "null":
        path = settings.get("log.dir")
    return path, settings.get("metadata.log.dir")


def parse_offsets(text):
    offsets = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([^:]+):(\d+):(-?\d+)", line.strip())
        if match and not match[1].startswith("__"):
            offsets[f"{match[1]}:{match[2]}"] = int(match[3])
    return offsets


def parse_consumers(text):
    offsets = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2].isdigit() and (parts[3].isdigit() or parts[3] == "-"):
            offsets[":".join(parts[:3])] = parts[3]
    return offsets


def snapshot():
    return {
        "topics": sorted(line.strip() for line in kafka("kafka-topics.sh", "--list").splitlines() if line.strip()),
        "earliest": parse_offsets(kafka("kafka-get-offsets.sh", "--time", "-2")),
        "latest": parse_offsets(kafka("kafka-get-offsets.sh", "--time", "-1")),
        "groups": sorted(line.strip() for line in kafka("kafka-consumer-groups.sh", "--list").splitlines() if line.strip()),
        "committed": parse_consumers(kafka("kafka-consumer-groups.sh", "--all-groups", "--describe")),
    }


def normalize_archive(raw):
    """Accept only directories/regular files and normalize Docker cp's root."""
    source = io.BytesIO(raw) if isinstance(raw, bytes) else raw
    with tarfile.open(fileobj=source, mode="r|*") as archive:
        output = io.BytesIO()
        manifest = {}
        with tarfile.open(fileobj=output, mode="w:gz", compresslevel=6) as target:
            for member in archive:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isdir() or member.isfile()):
                    raise ValueError("Unexpected path or file type in Kafka archive")
                if path.parts and path.parts[0] == "kafka-logs":
                    path = path.relative_to("kafka-logs")
                if str(path) == ".":
                    continue
                name = str(path)
                member.name = name
                if member.isfile():
                    if name in manifest:
                        raise ValueError("Duplicate Kafka archive member")
                    digest = hashlib.sha256()

                    class Reader:
                        def __init__(self, wrapped):
                            self.wrapped = wrapped

                        def read(self, size=-1):
                            data = self.wrapped.read(size)
                            digest.update(data)
                            return data

                    target.addfile(member, Reader(archive.extractfile(member)))
                    manifest[name] = digest.hexdigest()
                else:
                    target.addfile(member)
        if "meta.properties" not in manifest:
            raise ValueError("Archive lacks Kafka meta.properties; original container must be kept")
        if not any(name.startswith("__cluster_metadata-0/") for name in manifest):
            raise ValueError("Archive lacks KRaft metadata; migration stopped")
        return output.getvalue(), manifest


def stopped_archive():
    # Stream Docker's potentially >1 GB sparse-index archive into compression;
    # do not hold an uncompressed archive or write plaintext on the host disk.
    process = subprocess.Popen(["docker", "cp", "cnc-kafka:" + SOURCE + "/.", "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=security.ROOT)
    try:
        result = normalize_archive(process.stdout)
        process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError("Could not archive the stopped Kafka container")
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()


def wait_ready():
    for attempt in range(90):
        try:
            kafka("kafka-topics.sh", "--list")
            return
        except RuntimeError:
            if attempt == 89:
                raise RuntimeError("Kafka did not become ready; encrypted migration backup retained") from None
            time.sleep(2)


def main():
    os.environ.setdefault("SOPS_AGE_KEY_FILE", str(security.default_age_key()))
    values = security.decrypt()
    original = inspect("cnc-kafka")
    mounts = [mount for mount in original["Mounts"] if mount["Destination"] == TARGET and mount["Type"] == "volume"]
    if len(mounts) != 1:
        raise RuntimeError("Expected exactly one named Kafka volume at " + TARGET)
    volume = mounts[0]["Name"]
    project = original["Config"]["Labels"].get("com.docker.compose.project")
    if not project or volume != project + "_kafka-data":
        raise RuntimeError("Kafka volume does not match this Compose project")
    active, metadata = storage_settings()
    if active == TARGET and metadata in ("null", None, TARGET):
        print("Kafka already uses the persistent volume; no migration performed.")
        return
    if active != SOURCE or metadata not in ("null", None, SOURCE):
        raise RuntimeError("Unexpected active Kafka storage paths; no data has been moved")
    if configure_nifi.STATE.exists():
        raise RuntimeError("Another NiFi migration is pending; preserve its state before migrating Kafka")
    docker("exec", "cnc-kafka", "sh", "-c", 'test -z "$(ls -A /var/lib/kafka/data)"')
    owner = docker("exec", "cnc-kafka", "stat", "-c", "%u:%g", SOURCE).decode().strip()
    if not re.fullmatch(r"\d+:\d+", owner):
        raise RuntimeError("Cannot determine the Kafka data owner")
    folder = security.ROOT / "secrets/kafka-migration"
    security.secure_directory(folder)
    journal = folder / "active.json"
    if journal.exists():
        raise RuntimeError("A migration journal already exists; recover it before retrying")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {"volume": volume, "source": SOURCE, "target": TARGET,
              "originalContainer": original["Id"], "filebeatWasRunning": inspect("cnc-filebeat")["State"]["Running"]}

    def phase(name):
        record["phase"] = name
        journal.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("Kafka migration: " + name, flush=True)

    phase("prepared")
    if record["filebeatWasRunning"]:
        docker("stop", "--time", "30", "cnc-filebeat")
    api = configure_nifi.NiFi(values)
    configure_nifi.pause(api)
    before = snapshot()
    record["before"] = before
    phase("ingestion-paused-and-offsets-recorded")
    docker("stop", "--time", "90", "cnc-kafka")
    stopped = inspect("cnc-kafka")["State"]
    if stopped["Running"] or stopped["ExitCode"] == 137:
        raise RuntimeError("Kafka did not stop cleanly; original container has been preserved")
    phase("broker-stopped")
    archive, manifest = stopped_archive()
    backup = folder / f"kafka-before-persistence-{stamp}.enc.json"
    recipient = security.captured(["age-keygen", "-y", os.environ["SOPS_AGE_KEY_FILE"]]).decode().strip()
    encrypted = security.captured(["sops", "encrypt", "--age", recipient, "--input-type", "binary",
                                  "--output-type", "json", "--filename-override", str(security.ENCRYPTED)], data=archive)
    with backup.open("xb") as output:
        output.write(encrypted)
    restored = security.captured(["sops", "decrypt", "--output-type", "binary", str(backup)])
    if hashlib.sha256(restored).digest() != hashlib.sha256(archive).digest():
        raise RuntimeError("Encrypted Kafka backup verification failed; original container retained")
    record.update(backup=backup.name, files=len(manifest), archiveSha256=hashlib.sha256(archive).hexdigest())
    phase("encrypted-backup-recovery-verified")
    image = original["Config"]["Image"]
    helper = ["run", "--rm", "-i", "--user", "0:0", "--network", "none", "--mount",
              f"type=volume,source={volume},target=/target", "--entrypoint", "/bin/bash", image]
    docker(*helper, "-c", 'set -e; test -z "$(ls -A /target)"; tar -xzpf - -C /target; chown -R "$1" /target',
           "--", owner, data=archive)
    readback = docker(*helper, "-c", "tar -czpf - -C /target .")
    _, copied = normalize_archive(readback)
    if copied != manifest:
        raise RuntimeError("Kafka data copy checksums differ; original container retained")
    phase("persistent-volume-file-checksums-verified")
    runtime = security.runtime_path()
    security.materialize(values, runtime)
    security.compose(values, runtime, ["up", "-d", "--force-recreate", "--no-deps", "kafka"])
    wait_ready()
    if storage_settings() != (TARGET, TARGET):
        raise RuntimeError("Recreated Kafka did not select the persistent storage paths")
    if snapshot() != before:
        raise RuntimeError("Topics or consumer offsets differ after migration; ingestion remains paused")
    phase("first-recreation-topics-and-offsets-verified")
    # Recreate once more with no ingestion: the data must survive independently
    # of the new container's writable layer as well.
    security.compose(values, runtime, ["up", "-d", "--force-recreate", "--no-deps", "kafka"])
    wait_ready()
    if snapshot() != before:
        raise RuntimeError("Persistence verification failed after a second recreation")
    phase("second-recreation-persistence-verified")
    configure_nifi.resume(api)
    if record["filebeatWasRunning"]:
        docker("start", "cnc-filebeat")
    phase("completed")
    journal.replace(folder / f"completed-{stamp}.json")
    print(f"Verified {len(manifest)} files, {len(before['topics'])} topics and {len(before['committed'])} committed partition offsets. Original data survived two container recreations. Ingestion resumed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, tarfile.TarError) as error:
        print(f"Kafka migration stopped: {error}. Preserve the original container/volume and secrets/kafka-migration recovery files.", file=sys.stderr)
        sys.exit(1)
