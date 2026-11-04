"""Deploy a full GHCR commit SHA to the fixed library-staging environment.

Install alongside staging_smoke.py in root-owned /opt/library-staging.
Run on Ubuntu as root. No arbitrary commands or configuration paths are accepted.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from staging_smoke import check_release, require

ROOT = Path("/opt/library-staging")
STATE = ROOT / "releases"
IMAGE = "ghcr.io/ssofpv/library-devops:"
DB_CONTAINER = "library-staging-db-1"
DB_USER = "library_staging"
DB_NAME = "library_staging"
BASE_URL = "http://192.168.56.10:18000"
DOCKER = "/usr/bin/docker"


def valid_sha(value):
    require(re.fullmatch(r"[0-9a-f]{40}", value), "Expected a full lowercase commit SHA")
    return value


def run(arguments, *, env, stdin=None, stdout=None, capture=False):
    return subprocess.run(
        arguments,
        env=env,
        stdin=stdin,
        stdout=subprocess.PIPE if capture else stdout,
        check=True,
        timeout=1800,
    )


def compose(env, *arguments, **kwargs):
    return run(
        [
            DOCKER,
            "compose",
            "--env-file",
            str(ROOT / ".env.staging"),
            "-f",
            str(ROOT / "compose.staging.yaml"),
            *arguments,
        ],
        env=env,
        **kwargs,
    )


def db(env, *arguments, **kwargs):
    return run([DOCKER, "exec", "-i", DB_CONTAINER, *arguments], env=env, **kwargs)


def backup_and_verify(env, release):
    backup = release / "database.dump"
    with backup.open("xb") as output:
        db(env, "pg_dump", "-U", DB_USER, "-d", DB_NAME, "-Fc", stdout=output)
    require(backup.stat().st_size > 0, "Database backup is empty")
    temporary_db = "lr6_restore_" + uuid4().hex
    db(env, "createdb", "-U", DB_USER, "-T", "template0", temporary_db)
    try:
        with backup.open("rb") as source:
            db(
                env,
                "pg_restore",
                "-U",
                DB_USER,
                "-d",
                temporary_db,
                "--exit-on-error",
                "--single-transaction",
                stdin=source,
            )
        sql = (
            "SELECT row_to_json(c)::text FROM inventory_copy c WHERE inventory_number = 'LR6-001';"
        )
        records = []
        for name in [DB_NAME, temporary_db]:
            result = db(
                env,
                "psql",
                "-U",
                DB_USER,
                "-d",
                name,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
                capture=True,
            )
            records.append(result.stdout.strip())
        require(records[0] and records[0] == records[1], "Backup fixture verification failed")
    finally:
        db(env, "dropdb", "-U", DB_USER, temporary_db)
    print("Database backup and separate restore: OK", flush=True)


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def deploy(revision, env):
    credentials = json.loads((ROOT / ".smoke.json").read_text(encoding="utf-8"))
    for field in ["username", "password"]:
        require(
            isinstance(credentials.get(field), str) and credentials[field],
            "Missing smoke-test credentials",
        )
    settings_path = ROOT / ".env.staging"
    settings = settings_path.read_text(encoding="utf-8")
    require(
        len(re.findall(r"^APP_IMAGE_TAG=.*$", settings, flags=re.MULTILINE)) == 1,
        "Expected exactly one APP_IMAGE_TAG setting",
    )
    compose(env, "config", "--quiet")
    container = compose(env, "ps", "-q", "app", capture=True).stdout.decode().strip()
    require(container and "\n" not in container, "Expected one running staging app")
    previous = (
        run(
            [DOCKER, "inspect", "--format", "{{.Config.Image}}", container],
            env=env,
            capture=True,
        )
        .stdout.decode()
        .strip()
    )
    require(previous.startswith(IMAGE), "Unexpected current staging image")
    valid_sha(previous.removeprefix(IMAGE))

    # Pull failure must leave the running release untouched.
    compose(env, "pull", "app")
    release = STATE / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    release.mkdir(parents=True, mode=0o700)
    metadata = {
        "requested_sha": revision,
        "previous_image": previous,
        "backup": str(release / "database.dump"),
        "status": "preparing",
    }
    save_json(release / "release.json", metadata)
    try:
        backup_and_verify(env, release)
        # Do not apply unknown schema changes automatically. A migration needs a
        # reviewed forward/rollback plan before enabling it for this environment.
        compose(
            env,
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "app",
            "python",
            "manage.py",
            "migrate",
            "--check",
        )
        metadata["status"] = "deploying"
        save_json(release / "release.json", metadata)
        compose(
            env,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            "app",
        )
        check_release(BASE_URL, revision, credentials["username"], credentials["password"])
        updated = re.sub(
            r"^APP_IMAGE_TAG=.*$", "APP_IMAGE_TAG=" + revision, settings, flags=re.MULTILINE
        )
        temporary = ROOT / ".env.staging.tmp"
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(settings_path)
        metadata["status"] = "accepted"
        save_json(release / "release.json", metadata)
        save_json(STATE / "last-success.json", metadata)
        print("RELEASE ACCEPTED", flush=True)
    except Exception:
        metadata["status"] = "failed"
        save_json(release / "release.json", metadata)
        print(f"Release failed. Previous image: {previous}", file=sys.stderr)
        print(f"Release record: {release / 'release.json'}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", type=valid_sha)
    args = parser.parse_args()
    require(sys.platform == "linux", "Deployment is supported only on the Ubuntu server")
    require(os.geteuid() == 0, "Run through the dedicated sudo rule")
    import fcntl

    os.umask(0o077)
    # Ignore caller-supplied Docker and Compose variables and executable paths.
    env = {"PATH": "/usr/bin:/bin", "HOME": "/root", "APP_IMAGE_TAG": args.revision}
    with (ROOT / ".deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another staging deployment is running") from None
        deploy(args.revision, env)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never emit credentials, environment dumps or HTTP response bodies.
        detail = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"RELEASE REJECTED: {detail}", file=sys.stderr)
        sys.exit(1)
