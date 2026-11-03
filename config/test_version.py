from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class VersionEndpointTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base_dir = Path(self.directory.name)
        self.settings_override = override_settings(BASE_DIR=self.base_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.version_file = self.base_dir / "build-version.txt"

    def test_returns_image_revision_without_login(self):
        revision = "a" * 40
        self.version_file.write_text(revision + "\n", encoding="utf-8")

        response = self.client.get(reverse("version"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"version": revision})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_missing_version_returns_503(self):
        response = self.client.get(reverse("version"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "version unavailable"})

    def test_invalid_versions_return_503(self):
        for value in ["", "latest", "a" * 39, "a" * 41, "g" * 40]:
            with self.subTest(value=value):
                self.version_file.write_text(value, encoding="utf-8")

                response = self.client.get(reverse("version"))

                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"error": "version unavailable"})

    def test_invalid_encoding_returns_503(self):
        self.version_file.write_bytes(b"\xff\xfe")

        response = self.client.get(reverse("version"))

        self.assertEqual(response.status_code, 503)

    def test_rejects_post(self):
        response = self.client.post(reverse("version"))

        self.assertEqual(response.status_code, 405)
