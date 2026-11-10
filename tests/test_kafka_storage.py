import hashlib
import io
import tarfile
import unittest
from scripts.migrate_kafka_storage import normalize_archive, parse_consumers, parse_offsets


def archive_bytes(prefix="", unsafe=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, content in (("meta.properties", b"cluster.id=test\nnode.id=1\n"),
                              ("__cluster_metadata-0/000.log", b"metadata"),
                              ("cnc-sensors-raw-0/000.log", b"test-records")):
            member = tarfile.TarInfo(prefix + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if unsafe:
            archive.addfile(unsafe)
    return output.getvalue()


class KafkaStorageTests(unittest.TestCase):
    def test_archive_normalization_preserves_cluster_and_record_bytes(self):
        normalized, manifest = normalize_archive(io.BytesIO(archive_bytes("kafka-logs/")))
        self.assertEqual(manifest["cnc-sensors-raw-0/000.log"], hashlib.sha256(b"test-records").hexdigest())
        self.assertIn("meta.properties", manifest)
        self.assertIn("__cluster_metadata-0/000.log", manifest)
        _, reread = normalize_archive(normalized)
        self.assertEqual(manifest, reread)

    def test_unexpected_archive_paths_and_links_are_rejected(self):
        for path in ("../outside", "/absolute"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                normalize_archive(archive_bytes(unsafe=tarfile.TarInfo(path)))
        member = tarfile.TarInfo("link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/outside"
        with self.assertRaises(ValueError):
            normalize_archive(archive_bytes(unsafe=member))

    def test_missing_cluster_metadata_is_rejected(self):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as archive:
            member = tarfile.TarInfo("meta.properties")
            archive.addfile(member, io.BytesIO(b""))
        with self.assertRaisesRegex(ValueError, "KRaft"):
            normalize_archive(output.getvalue())

    def test_business_offsets_and_committed_consumer_offsets_are_parsed(self):
        self.assertEqual(parse_offsets("cnc-sensors-raw:0:1234\n__consumer_offsets:0:50\n"), {"cnc-sensors-raw:0": 1234})
        table = "GROUP TOPIC PARTITION CURRENT-OFFSET LOG-END-OFFSET LAG\nnifi-consumer-group cnc-sensors-raw 0 1234 1240 6\n"
        self.assertEqual(parse_consumers(table), {"nifi-consumer-group:cnc-sensors-raw:0": "1234"})


if __name__ == "__main__":
    unittest.main()
