import unittest
import urllib.parse
from scripts.rotate_credentials import clean_mongo_uri, validate_username


class CredentialRotationTests(unittest.TestCase):
    def test_uri_removes_embedded_credentials_and_preserves_connection_options(self):
        uri = clean_mongo_uri("mongodb://old-user:old%40password@mongodb:27017/errors?authSource=old&retryWrites=false&authMechanism=SCRAM-SHA-256")
        parsed = urllib.parse.urlsplit(uri)
        self.assertIsNone(parsed.username)
        self.assertIsNone(parsed.password)
        self.assertEqual(parsed.netloc, "mongodb:27017")
        self.assertEqual(parsed.path, "/errors")
        self.assertEqual(urllib.parse.parse_qs(parsed.query), {"authSource": ["admin"], "retryWrites": ["false"]})

    def test_invalid_usernames_or_uris_fail_before_modifications(self):
        for username in ("", "a\nb", "a b", "../admin"):
            with self.subTest(username=username), self.assertRaises(ValueError):
                validate_username(username)
        validate_username("cncviewer")
        with self.assertRaises(ValueError):
            clean_mongo_uri("https://mongodb")


if __name__ == "__main__":
    unittest.main()
