"""Deployment failure barriers, without a Docker daemon or live database."""

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CalledProcessError
from types import SimpleNamespace
from unittest.mock import patch

import deploy_staging as deploy


class DeploymentTests(unittest.TestCase):
    revision = "a" * 40
    previous = "b" * 40

    def test_only_full_lowercase_sha_is_accepted(self):
        self.assertEqual(deploy.valid_sha(self.revision), self.revision)
        for value in ["main", "latest", "a" * 39, "A" * 40, "a" * 40 + ";id", "--help"]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                deploy.valid_sha(value)

    def exercise(self, failure):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            settings = "APP_IMAGE_TAG=" + self.previous + "\n"
            (root / ".env.staging").write_text(settings, encoding="utf-8")
            (root / ".smoke.json").write_text(
                json.dumps({"username": "test-user", "password": "test-only-value"}),
                encoding="utf-8",
            )
            events = []

            def compose(env, *args, **kwargs):
                events.append(args)
                if args[0] == failure:
                    raise CalledProcessError(1, ["docker", "compose", args[0]])
                return SimpleNamespace(stdout=b"container-id\n")

            with (
                patch.object(deploy, "ROOT", root),
                patch.object(deploy, "STATE", root / "releases"),
                patch.object(deploy, "compose", side_effect=compose),
                patch.object(
                    deploy,
                    "run",
                    return_value=SimpleNamespace(stdout=(deploy.IMAGE + self.previous).encode()),
                ),
                patch.object(deploy, "backup_and_verify") as backup,
                patch.object(deploy, "check_release") as acceptance,
            ):
                if failure == "acceptance":
                    acceptance.side_effect = RuntimeError("Test scenario failed")
                if failure:
                    with self.assertRaises((RuntimeError, CalledProcessError)):
                        deploy.deploy(self.revision, {})
                    self.assertEqual((root / ".env.staging").read_text(), settings)
                    self.assertFalse((root / "releases" / "last-success.json").exists())
                else:
                    deploy.deploy(self.revision, {})
                    self.assertEqual(
                        (root / ".env.staging").read_text(),
                        "APP_IMAGE_TAG=" + self.revision + "\n",
                    )
                    record = json.loads((root / "releases" / "last-success.json").read_text())
                    self.assertEqual(record["status"], "accepted")
                    self.assertEqual(record["previous_image"], deploy.IMAGE + self.previous)
                if failure == "pull":
                    backup.assert_not_called()
                    acceptance.assert_not_called()
                    self.assertFalse(any(event[0] == "up" for event in events))
                if failure == "run":
                    acceptance.assert_not_called()
                    self.assertFalse(any(event[0] == "up" for event in events))

    def test_registry_failure_does_not_replace_container(self):
        self.exercise("pull")

    def test_pending_migrations_block_container_replacement(self):
        self.exercise("run")

    def test_failed_acceptance_never_records_success(self):
        self.exercise("acceptance")

    def test_success_records_previous_image_and_requested_sha(self):
        self.exercise(None)


if __name__ == "__main__":
    unittest.main()
