"""Check the library container environment in disposable Compose projects."""

import argparse
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


class CheckError(Exception):
    """An acceptance requirement was not met."""


def require(condition, message):
    if not condition:
        raise CheckError(message)


def step(message):
    print(f"[container-check] {message}", flush=True)


def nonroot(user):
    name = str(user or "").split(":", 1)[0]
    return bool(name) and name != "root" and not (name.isdigit() and int(name) == 0)


def check_source(root):
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8-sig")
    instructions = re.sub(r"\\\r?\n", " ", dockerfile).splitlines()
    instructions = [line.strip() for line in instructions if line.strip()]
    bases = [line.split()[1] for line in instructions if line.upper().startswith("FROM ")]
    require(bases, "Dockerfile must contain FROM")
    for base in bases:
        require(
            re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", base),
            "Every base image must be pinned by a SHA256 digest",
        )
        require(":latest@" not in base.lower(), "The latest tag is forbidden")
    users = [line.split()[1] for line in instructions if line.upper().startswith("USER ")]
    require(users and nonroot(users[-1]), "The final Dockerfile USER must be non-root")
    require(
        any(line.upper().startswith("HEALTHCHECK ") for line in instructions),
        "Dockerfile must define a healthcheck",
    )
    require(
        not any(line.upper().startswith("HEALTHCHECK NONE") for line in instructions),
        "Disabling healthchecks is forbidden",
    )
    for line in instructions:
        if line.upper().startswith(("ENV ", "ARG ")):
            require(
                not re.search(r"\b\w*(SECRET|PASSWORD|TOKEN|PRIVATE_KEY)\w*\b", line, re.I),
                "Secret variables must not be declared in Dockerfile ENV or ARG",
            )
        if line.upper().startswith("RUN "):
            assignments = re.findall(
                r"\b(DJANGO_SECRET_KEY|POSTGRES_PASSWORD|\w*TOKEN)\s*=\s*([^\s]+)",
                line,
                re.I,
            )
            for key, value in assignments:
                require(
                    key == "DJANGO_SECRET_KEY"
                    and value == "public-build-placeholder"
                    and "manage.py collectstatic" in line,
                    "Secret assignments in build commands are forbidden",
                )
    require((root / ".dockerignore").is_file(), ".dockerignore is required")
    require((root / "compose.yaml").is_file(), "compose.yaml is required")
    for line in (root / "requirements.txt").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            require(
                re.fullmatch(r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.+-]+", line),
                "Runtime requirements must use exact versions",
            )


def check_policy(config, expected, project):
    services = config.get("services", {})
    require(set(services) == {"app", "db"}, "Expected exactly the app and db services")
    networks = config.get("networks", {})
    require(networks.get("backend", {}).get("internal") is True, "backend must be internal")
    for network in networks.values():
        require(not network.get("external"), "Check networks must not be external")
        require(
            str(network.get("name", "")).startswith(project + "_"),
            "Network names must be isolated by the Compose project",
        )
    volume = config.get("volumes", {}).get("postgres_data", {})
    require(not volume.get("external"), "Database volume must not be external")
    require(
        volume.get("name") == project + "_postgres_data",
        "Database volume must be isolated by the Compose project",
    )
    for name, service in services.items():
        image = service.get("image", "")
        image_tag = image.split("@", 1)[0].rsplit("/", 1)[-1]
        require(":" in image_tag, f"{name}: an explicit image tag is required")
        require(image_tag.rsplit(":", 1)[-1].lower() != "latest", f"{name}: latest forbidden")
        require(nonroot(service.get("user")), f"{name}: explicit non-root user required")
        require(not service.get("privileged"), f"{name}: privileged mode forbidden")
        require(not service.get("network_mode"), f"{name}: network_mode overrides forbidden")
        require(not service.get("pid"), f"{name}: PID namespace overrides forbidden")
        require(float(service.get("cpus", 0)) > 0, f"{name}: CPU limit required")
        require(int(service.get("mem_limit", 0)) > 0, f"{name}: memory limit required")
        health = service.get("healthcheck", {})
        require(not health.get("disable"), f"{name}: healthcheck cannot be disabled")
        require(health.get("test") != ["NONE"], f"{name}: healthcheck cannot be NONE")
        environment = service.get("environment", {})
        require(
            environment.get("POSTGRES_PASSWORD") == expected["POSTGRES_PASSWORD"],
            f"{name}: POSTGRES_PASSWORD must come from the environment",
        )
        for key in ("POSTGRES_DB", "POSTGRES_USER"):
            require(environment.get(key) == expected[key], f"{name}: {key} must be configurable")
    db = services["db"]
    require(
        re.search(r"@sha256:[0-9a-f]{64}$", db["image"]),
        "PostgreSQL image must be pinned by digest",
    )
    require(not db.get("ports"), "Publishing database ports is forbidden")
    require(set(db.get("networks", {})) == {"backend"}, "Database must use only backend")
    mounts = db.get("volumes", [])
    require(
        len(mounts) == 1
        and mounts[0].get("type") == "volume"
        and mounts[0].get("source") == "postgres_data"
        and mounts[0].get("target") == "/var/lib/postgresql/data",
        "PostgreSQL must store data in postgres_data, without host bind mounts",
    )
    require(db.get("healthcheck", {}).get("test"), "Database healthcheck is required")
    app = services["app"]
    require(not app.get("volumes"), "Unexpected application mounts are forbidden")
    require(
        app.get("depends_on", {}).get("db", {}).get("condition") == "service_healthy",
        "Application must wait for healthy PostgreSQL",
    )
    environment = app.get("environment", {})
    require(
        environment.get("DJANGO_SECRET_KEY") == expected["DJANGO_SECRET_KEY"],
        "DJANGO_SECRET_KEY must come from the environment",
    )
    require(str(environment.get("DJANGO_DEBUG", "")).lower() == "false", "DEBUG must be false")
    require(environment.get("DJANGO_DB_ENGINE") == "postgresql", "Application must use PostgreSQL")
    require(environment.get("POSTGRES_HOST") == "db", "Database host must be db")
    ports = app.get("ports", [])
    require(
        len(ports) == 1
        and int(ports[0].get("target", 0)) == 8000
        and ports[0].get("protocol", "tcp") == "tcp"
        and ports[0].get("host_ip") == "127.0.0.1",
        "Check application must publish only port 8000 on loopback",
    )


SEED = """
from catalog.models import Author, Book
from inventory.models import Branch, Copy
author = Author.objects.create(full_name="Container Check Author")
book = Book.objects.create(title="Container Check Book", description="Keep this data", publication_year=2026)
book.authors.add(author)
branch = Branch.objects.create(name="Container Check Branch", address="Check address")
Copy.objects.create(inventory_number="CONTAINER-CHECK-001", book=book, branch=branch, shelf_location="A-01")
"""

IMAGE_CHECK = """
import os
from pathlib import Path
for name in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"):
    if name in os.environ:
        raise SystemExit("Secret variable baked into image: " + name)
for path in Path("/app").rglob("*"):
    relative = path.relative_to("/app")
    if any(part in {".git", ".venv", "backups", ".ssh"} for part in relative.parts):
        raise SystemExit("Forbidden image path: " + str(relative))
    if path.is_file() and ((path.name.startswith(".env") and path.name != ".env.example")
                         or path.suffix in {".sqlite3", ".dump", ".backup", ".pem", ".key"}):
        raise SystemExit("Forbidden image file: " + str(relative))
print("Image files and secret environment: OK")
"""


class Checker:
    def __init__(self, root, docker, folder):
        self.root = root
        self.docker = shlex.split(docker)
        require(self.docker, "Docker command cannot be empty")
        self.project = "library-cc-" + secrets.token_hex(6)
        self.restore_project = self.project + "-restore"
        self.image = "library-container-check:" + self.project
        self.env = os.environ.copy()
        self.settings = {
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
            "DJANGO_DEBUG": "false",
            "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
            "POSTGRES_DB": "library_container_check",
            "POSTGRES_USER": "library_check",
            "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
            "APP_BIND_IP": "127.0.0.1",
            "APP_PORT": "0",
        }
        self.env.update(self.settings)
        self.envfile = folder / "check.env"
        self.envfile.write_text(
            "".join(f"{k}={v}\n" for k, v in self.settings.items()), encoding="utf-8"
        )
        self.envfile.chmod(0o600)
        self.override = folder / "check.yaml"
        self.override.write_text(f"services:\n  app:\n    image: {self.image}\n", encoding="utf-8")
        self.projects_started = []
        self.probe = root / (".env.container-check-probe-" + self.project)
        self.probe_owned = False
        self.secret_values = [
            self.settings["DJANGO_SECRET_KEY"],
            self.settings["POSTGRES_PASSWORD"],
        ]

    def redact(self, message):
        for value in self.secret_values:
            message = message.replace(value, "[REDACTED]")
        return message

    def command(self, arguments, input_data=None, timeout=180, check=True):
        result = subprocess.run(
            arguments,
            cwd=self.root,
            env=self.env,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode:
            detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            raise CheckError(
                self.redact(f"Command failed ({result.returncode}):\n" + detail[-12000:])
            )
        return result

    def compose(self, *arguments, restore=False, input_data=None, timeout=180, check=True):
        project = self.restore_project if restore else self.project
        prefix = self.docker + [
            "compose",
            "--project-directory",
            str(self.root),
            "--env-file",
            str(self.envfile),
            "-f",
            str(self.root / "compose.yaml"),
            "-f",
            str(self.override),
            "-p",
            project,
        ]
        return self.command(prefix + list(arguments), input_data, timeout, check)

    def text(self, result):
        return result.stdout.decode("utf-8").strip()

    def container_id(self, service, restore=False):
        identifier = self.text(self.compose("ps", "-a", "-q", service, restore=restore))
        require(identifier and "\n" not in identifier, f"Expected one {service} container")
        return identifier

    def inspect(self, service, restore=False):
        result = self.command(
            self.docker + ["inspect", self.container_id(service, restore=restore)]
        )
        return json.loads(result.stdout)[0]

    def start(self, *services, restore=False, no_deps=False):
        arguments = ["up", "-d"]
        if no_deps:
            arguments.append("--no-deps")
        self.compose(*arguments, *services, restore=restore)
        selected = services or ("app", "db")
        deadline = time.monotonic() + 120
        previous = None
        while time.monotonic() < deadline:
            statuses = {}
            for service in selected:
                state = self.inspect(service, restore=restore)["State"]
                statuses[service] = (
                    state.get("Status"),
                    state.get("Health", {}).get("Status"),
                )
            if statuses != previous:
                step(
                    "Readiness: "
                    + ", ".join(
                        f"{service}={status}/{health}"
                        for service, (status, health) in statuses.items()
                    )
                )
                previous = statuses
            if all(
                status == "running" and health == "healthy" for status, health in statuses.values()
            ):
                return
            time.sleep(1)
        raise CheckError(f"Services did not become healthy within 120 seconds: {statuses}")

    def wait_health(self, expected, timeout=75):
        started = time.monotonic()
        wall_started = time.time()
        deadline = started + timeout
        next_report = started
        previous = None
        details = None

        while time.monotonic() < deadline:
            inspect_started = time.monotonic()
            info = self.inspect("app")
            now = time.monotonic()
            health = info.get("State", {}).get("Health", {})
            status = health.get("Status")
            streak = health.get("FailingStreak")
            details = (status, streak)

            if details != previous or now >= next_report:
                step(
                    f"Waiting for {expected}: status={status}, "
                    f"failing_streak={streak}, "
                    f"elapsed={now - started:.1f}s, "
                    f"wall_elapsed={time.time() - wall_started:.1f}s, "
                    f"inspect_duration={now - inspect_started:.1f}s"
                )
                previous = details
                next_report = now + 10

            if status == expected:
                return
            time.sleep(1)

        raise CheckError(
            f"Application did not become {expected} within {timeout}s; last status/streak={details}"
        )

    def http(self):
        binding = self.text(self.compose("port", "app", "8000"))
        port = int(binding.rsplit(":", 1)[1])
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(f"http://127.0.0.1:{port}/health/", timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def snapshot(self, restore=False):
        if restore:
            command = ("run", "--rm", "--no-deps", "-T", "app")
        else:
            command = ("exec", "-T", "app")
        result = self.compose(*command, "python", "manage.py", "dumpdata", "--all", restore=restore)
        return json.loads(result.stdout)

    def build(self, revision):
        self.command(
            self.docker
            + [
                "build",
                "--label",
                f"org.library.container-check.revision={revision}",
                "-t",
                self.image,
                ".",
            ],
            timeout=900,
        )

    def runtime_policy(self, service):
        info = self.inspect(service)
        uid = self.text(self.compose("exec", "-T", service, "id", "-u"))
        require(uid.isdigit() and int(uid) > 0, f"{service}: runtime user must be non-root")
        pid_uid = self.text(
            self.compose(
                "exec",
                "-T",
                service,
                "sh",
                "-c",
                "awk '/^Uid:/ {print $2}' /proc/1/status",
            )
        )
        require(pid_uid.isdigit() and int(pid_uid) > 0, f"{service}: PID 1 must be non-root")
        health = info.get("Config", {}).get("Healthcheck", {})
        require(
            health.get("Test") and health["Test"] != ["NONE"],
            f"{service}: runtime healthcheck required",
        )
        host = info["HostConfig"]
        require(
            host.get("Memory", 0) > 0 and host.get("NanoCpus", 0) > 0,
            f"{service}: limits not applied",
        )
        require(not host.get("Privileged"), f"{service}: privileged runtime forbidden")
        if service == "db":
            require(not host.get("PortBindings"), "Database has published ports")
        step(
            f"{service}: process UID={pid_uid}, memory={host['Memory']} bytes, CPU={host['NanoCpus'] / 1e9:g}"
        )

    def run(self):
        step("Checker version: polling-v3")
        step("Checking Dockerfile and Compose policy")
        check_source(self.root)
        self.command(self.docker + ["version"], timeout=30)
        for restore, project in ((False, self.project), (True, self.restore_project)):
            config = json.loads(self.compose("config", "--format", "json", restore=restore).stdout)
            check_policy(config, self.settings, project)
        with self.probe.open("x", encoding="utf-8") as probe:
            self.probe_owned = True
            probe.write("MUST_NOT_BE_IN_IMAGE=" + secrets.token_hex(24))
        self.probe.chmod(0o600)
        step("Building disposable application image (revision 1)")
        self.build(1)
        self.command(
            self.docker + ["run", "--rm", "--entrypoint", "python", self.image, "-c", IMAGE_CHECK]
        )
        step("Starting isolated PostgreSQL and applying migrations")
        self.projects_started.append(False)
        step("Waiting for isolated PostgreSQL to become healthy")
        self.start("db")
        step("Applying migrations in the isolated database")
        self.compose(
            "run", "--rm", "--no-deps", "-T", "app", "python", "manage.py", "migrate", "--noinput"
        )
        step("Waiting for the application to become healthy")
        self.start("app", "db")
        for service in ("app", "db"):
            self.runtime_policy(service)
        require(self.http() == (200, {"status": "ok"}), "Health endpoint must return HTTP 200")
        self.compose("exec", "-T", "app", "python", "manage.py", "shell", "-c", SEED)
        before = self.snapshot()
        require(before, "Control dataset is empty")
        step("Checking data after recreating containers")
        self.compose("down")
        self.start()
        require(self.snapshot() == before, "Data changed after container recreation")
        old_image = self.inspect("app")["Image"]
        step("Building revision 2 and checking data after image replacement")
        self.build(2)
        self.start("app", no_deps=True)
        require(self.inspect("app")["Image"] != old_image, "Application image was not replaced")
        require(self.snapshot() == before, "Data changed after image replacement")
        step("Backing up PostgreSQL and restoring into a new isolated volume")
        dump = self.compose(
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            self.settings["POSTGRES_USER"],
            "-d",
            self.settings["POSTGRES_DB"],
            "-Fc",
        ).stdout
        require(dump.startswith(b"PGDMP"), "PostgreSQL backup is not a custom archive")
        self.projects_started.append(True)
        self.start("db", restore=True)
        self.compose(
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            self.settings["POSTGRES_USER"],
            "-d",
            self.settings["POSTGRES_DB"],
            "--no-owner",
            "--no-privileges",
            "--single-transaction",
            restore=True,
            input_data=dump,
        )
        require(self.snapshot(restore=True) == before, "Restored data differs from the original")
        self.compose("stop", "db", restore=True)
        step("Checking HTTP 503 and unhealthy status while PostgreSQL is stopped")
        self.compose("stop", "db")
        require(
            self.http() == (503, {"status": "error", "database": "unavailable"}),
            "Health endpoint must return HTTP 503 when database is unavailable",
        )
        self.wait_health("unhealthy")
        self.start("db")
        self.wait_health("healthy")
        require(
            self.http() == (200, {"status": "ok"}), "Health did not recover after database restart"
        )
        step("Recording resource use and checking graceful application shutdown")
        stats = self.command(
            self.docker
            + [
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}: {{.MemUsage}}; CPU {{.CPUPerc}}",
                self.container_id("app"),
                self.container_id("db"),
            ]
        )
        print(self.text(stats), flush=True)
        self.compose("stop", "app", timeout=65)
        state = self.inspect("app")["State"]
        require(
            state.get("ExitCode") == 0 and not state.get("OOMKilled"),
            "Application did not exit cleanly",
        )
        logs = self.compose("logs", "--no-color", "app")
        log_text = (logs.stdout + logs.stderr).decode("utf-8", errors="replace")
        require(
            "Handling signal: term" in log_text and "Shutting down: Master" in log_text,
            "Gunicorn graceful shutdown was not confirmed in logs",
        )

    def cleanup(self):
        errors = []
        for restore in reversed(self.projects_started):
            try:
                result = self.compose(
                    "down", "--volumes", "--remove-orphans", restore=restore, check=False
                )
                if result.returncode:
                    errors.append("Could not remove an isolated check project")
            except (OSError, subprocess.TimeoutExpired):
                errors.append("Cleanup command failed")
        if self.probe_owned and self.probe.exists():
            self.probe.unlink()
        self.command(self.docker + ["image", "rm", self.image], timeout=60, check=False)
        return errors

    def diagnostics(self):
        if not self.projects_started:
            return
        step("Failure diagnostics before cleanup")
        for restore in self.projects_started:
            project = self.restore_project if restore else self.project
            print(f"Project: {project}", flush=True)
            try:
                result = self.compose(
                    "logs",
                    "--no-color",
                    "--tail",
                    "60",
                    restore=restore,
                    timeout=30,
                    check=False,
                )
                detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
                print(self.redact(detail[-12000:]), flush=True)
            except (OSError, subprocess.TimeoutExpired) as error:
                print(self.redact(f"Could not read logs: {error}"), flush=True)
        try:
            state = self.inspect("app")["State"]
            print("Application state: " + self.redact(json.dumps(state)), flush=True)
        except (CheckError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            print(self.redact(f"Could not read application state: {error}"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docker", default="docker", help='Docker command, for example "sudo docker"'
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository directory")
    arguments = parser.parse_args()
    checker = None
    failure = None
    with tempfile.TemporaryDirectory(prefix="library-container-check-") as temporary:
        try:
            checker = Checker(arguments.root.resolve(), arguments.docker, Path(temporary))
            checker.run()
        except (
            CheckError,
            OSError,
            ValueError,
            KeyError,
            subprocess.TimeoutExpired,
            urllib.error.URLError,
            KeyboardInterrupt,
        ) as error:
            failure = str(error) or type(error).__name__
            if checker:
                failure = checker.redact(failure)
                checker.diagnostics()
        finally:
            if checker:
                step("Cleaning up only the generated check projects")
                try:
                    cleanup_errors = checker.cleanup()
                    if cleanup_errors:
                        failure = (failure + "; " if failure else "") + "; ".join(cleanup_errors)
                except (OSError, subprocess.TimeoutExpired) as error:
                    failure = (failure + "; " if failure else "") + "Cleanup failed: " + str(error)
    if failure:
        print("CONTAINER_CHECK_FAILED: " + failure, file=sys.stderr)
        return 1
    print("CONTAINER_CHECK_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
