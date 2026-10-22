"""Bounded ephemeral services; execution always requires the separate manual gate."""

import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlunsplit

from gate import Blocked, execution_gate, resources

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from acceptance.p0_diagnostics import (  # noqa: E402
    SEED_STAGE,
    public_diagnostic,
    seed_outcome,
    validate_result_diagnostic,
)

PRIVATE = ROOT / ".local/p0-private"
EVIDENCE = ROOT / ".local/p0-evidence"
PYTHON = ROOT / "backend/.venv/bin/python"
DB_NAME = "finleak_product_v11_test"
CONTAINER = "finleak-p0-postgres"
PG_IMAGE = (
    "docker.io/library/postgres@"
    "sha256:ec4dfc6571f04fe0731ce948c1500d676af49a7224392dcc6995cc1ee33a94bb"
)


class SeedFailure(Exception):
    def __init__(self, status, diagnostic):
        super().__init__("Synthetic fixture did not complete")
        self.status = status
        self.diagnostic = diagnostic


def database_url(user, password):
    return urlunsplit(
        (
            "postgresql+psycopg",
            user + ":" + quote(password, safe="") + "@127.0.0.1:5432",
            "/" + DB_NAME,
            "",
            "",
        )
    )


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o600)


def base_env():
    # Explicit allow-list: no GitHub token, cloud credentials or inherited client secrets.
    return {
        k: os.environ[k]
        for k in ("PATH", "HOME", "LANG", "PLAYWRIGHT_BROWSERS_PATH")
        if k in os.environ
    }


def load_env():
    return json.loads((PRIVATE / "environment.json").read_text())


def backend_start(env):
    process = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
            "--log-level",
            "warning",
        ],
        cwd=ROOT / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    write(PRIVATE / "backend.json", {"pid": process.pid})
    return process


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def ready(url, seconds=35):
    deadline = time.monotonic() + seconds
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.2)
    raise Blocked(
        "Loopback development service did not become ready within its deadline"
    )


def restart_backend():
    execution_gate(ROOT)
    env = load_env()
    kill_group(json.loads((PRIVATE / "backend.json").read_text())["pid"])
    backend_start(env)
    ready("http://127.0.0.1:8000/openapi.json", 20)
    print(json.dumps({"status": "BACKEND_RESTARTED", "database_restarted": False}))


def cleanup():
    if not PRIVATE.exists():
        return
    for name in ("backend", "frontend", "oidc"):
        path = PRIVATE / (name + ".json")
        if path.exists():
            kill_group(json.loads(path.read_text())["pid"])
    expected = json.loads((PRIVATE / "instance.json").read_text())["id"]
    found = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "finleak.p0.instance"}}',
            CONTAINER,
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if found.returncode == 0 and found.stdout.strip() == expected:
        subprocess.run(
            ["docker", "rm", "-f", CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
    shutil.rmtree(PRIVATE)
    fixture = ROOT / ".local/product-v11"
    if fixture.exists():
        shutil.rmtree(fixture)


def execute():
    result = {
        "status": "BLOCKED",
        "synthetic": True,
        "e2e_executed": False,
        "qualification_phase7": False,
        "steps": [],
        "migration_0010": "NOT APPLIED",
    }
    processes = []
    owns_resources = False
    stage = "authorization_and_resources"
    try:
        execution_gate(ROOT)
        result["resources_before"] = resources(ROOT)
        started = float(os.environ["P0_JOB_STARTED_EPOCH"])
        deadline = started + 510  # Leave 90 seconds for sanitized receipt and cleanup.
        if time.time() > deadline - 150:
            raise Blocked(
                "Insufficient time remaining inside the single ten-minute job"
            )
        if PRIVATE.exists() or (ROOT / ".local/product-v11/roster.json").exists():
            raise Blocked("Fresh disposable workspace required")
        for base in (ROOT, ROOT / "frontend"):
            if any(
                p.is_file() and p.name != ".env.example" for p in base.glob(".env*")
            ):
                raise Blocked(
                    "Active environment file found; synthetic-only workspace required"
                )
        if platform.python_version() != "3.12.15" or sys.flags.optimize:
            raise Blocked("Pinned CPython 3.12.15 required")
        PRIVATE.mkdir(parents=True, mode=0o700)
        owns_resources = True
        instance_id = secrets.token_hex(16)
        write(PRIVATE / "instance.json", {"id": instance_id})
        env = base_env()
        (PRIVATE / "docker-config").mkdir(mode=0o700)
        env["DOCKER_CONFIG"] = str(PRIVATE / "docker-config")
        env["DOCKER_HOST"] = "unix:///var/run/docker.sock"
        secret, db_password, admin_password, migration_password = (
            secrets.token_hex(32) for _ in range(4)
        )
        config = {
            "synthetic": True,
            "client_secret": secret,
            "accounts": {
                role: {
                    "password": secrets.token_hex(32),
                    "subject": "p0-synthetic-" + role,
                    "name": "Synthetic P0 " + role.title(),
                }
                for role in ("owner", "analyst")
            },
        }
        write(PRIVATE / "oidc-config.json", config)
        env.update(
            P0_EXECUTION="1",
            GITHUB_ACTIONS="true",
            CI="true",
            FLA_ENVIRONMENT="test",
            P0_OIDC_CONFIG_FILE=str(PRIVATE / "oidc-config.json"),
            PRODUCT_V11_ACCEPTANCE="1",
            PRODUCT_SYNTHETIC_ACCOUNTS_ONLY="1",
            PRODUCT_OWNER_SUBJECT=config["accounts"]["owner"]["subject"],
            PRODUCT_ANALYST_SUBJECT=config["accounts"]["analyst"]["subject"],
            PRODUCT_OWNER_USERNAME="owner",
            PRODUCT_ANALYST_USERNAME="analyst",
            PRODUCT_OWNER_PASSWORD=config["accounts"]["owner"]["password"],
            PRODUCT_ANALYST_PASSWORD=config["accounts"]["analyst"]["password"],
            OIDC_ISSUER_URL="http://127.0.0.1:9100",
            OIDC_AUDIENCE="finleak-p0-api",
            OIDC_CLIENT_ID="finleak-p0-browser",
            OIDC_CLIENT_SECRET=secret,
            NEXTAUTH_URL="http://127.0.0.1:3000",
            NEXTAUTH_SECRET=secrets.token_hex(32),
            BACKEND_URL="http://127.0.0.1:8000",
            PRODUCT_FRONTEND_URL="http://127.0.0.1:3000",
            FLA_DATABASE_URL=database_url("finleak_p0", db_password),
            FLA_STORAGE_ROOT=str(ROOT / ".local/product-v11/originals"),
            FLA_SCANNER_BACKEND="unconfigured",
            FLA_LOG_LEVEL="ERROR",
            PYTHONPATH=str(ROOT / "backend"),
            PRODUCT_PYTHON=str(PYTHON),
            NEXT_TELEMETRY_DISABLED="1",
            NODE_ENV="development",
            NODE_OPTIONS="--max-old-space-size=1536",
        )
        write(PRIVATE / "environment.json", env)
        # Restart control needs only these execution guards, never GITHUB_TOKEN.
        for k in (
            "GITHUB_EVENT_NAME",
            "GITHUB_ACTOR",
            "GITHUB_RUN_ATTEMPT",
            "GITHUB_SHA",
            "GITHUB_REPOSITORY",
            "P0_RUNNER_KIND",
            "P0_AUTHORIZATION",
            "P0_EXPECTED_COMMIT",
            "P0_BILLING_SHA256",
        ):
            env[k] = os.environ[k]
        write(PRIVATE / "environment.json", env)

        migration_url = database_url("p0_migrator", migration_password)

        def run(label, command, cwd=ROOT, timeout=40, input_=None, extra_env=None):
            nonlocal stage
            stage = label
            current = time.monotonic()
            remaining = min(timeout, deadline - time.time())
            if remaining <= 0:
                raise Blocked("Global execution deadline reached")
            available = (
                int(
                    next(
                        line.split()[1]
                        for line in Path("/proc/meminfo").read_text().splitlines()
                        if line.startswith("MemAvailable:")
                    )
                )
                * 1024
            )
            if available < 512 * 1024**2 or shutil.disk_usage(ROOT).free < 2 * 1024**3:
                raise Blocked(
                    "Resource reserve exhausted; no runner resizing permitted"
                )
            try:
                done = subprocess.run(
                    command,
                    cwd=cwd,
                    env={**env, **(extra_env or {})},
                    input=input_,
                    capture_output=True,
                    timeout=remaining,
                    check=False,
                )
            except (subprocess.TimeoutExpired, OSError) as error:
                if label != SEED_STAGE:
                    raise
                result["steps"].append(
                    {
                        "stage": label,
                        "exit_code": None,
                        "seconds": round(time.monotonic() - current, 3),
                    }
                )
                status, diagnostic = seed_outcome(
                    None,
                    timeout=isinstance(error, subprocess.TimeoutExpired),
                    unavailable=isinstance(error, OSError),
                )
                raise SeedFailure(status, diagnostic) from None
            result["steps"].append(
                {
                    "stage": label,
                    "exit_code": done.returncode,
                    "seconds": round(time.monotonic() - current, 3),
                }
            )
            if label == SEED_STAGE:
                status, diagnostic = seed_outcome(done.returncode, done.stdout)
                result["fixture_diagnostic"] = diagnostic
                if status != "FIXTURE_ONLY":
                    raise SeedFailure(status, diagnostic)
            if done.returncode:
                raise RuntimeError("Candidate stage failed")
            return done.stdout

        node_version = run("node_version", ["node", "--version"]).decode().strip()
        uv_version = run("uv_version", ["uv", "--version"]).decode().strip()
        if node_version != "v24.21.0" or uv_version.split()[1] != "0.12.19":
            raise Blocked("Candidate tool versions disagree with reviewed pins")
        result["runtime_versions"] = {
            "python": platform.python_version(),
            "node": node_version,
            "uv": uv_version,
        }
        catalog = ROOT / "frontend/node_modules/playwright-core/browsers.json"
        pins = json.loads((ROOT / "bench/p0/pins.json").read_text())
        catalog_digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
        if catalog_digest != pins["playwright_browsers_json_sha256"]:
            raise Blocked("Pinned Playwright browser catalog disagrees")
        cache = Path(env["PLAYWRIGHT_BROWSERS_PATH"]).resolve()
        binaries = [p for p in cache.rglob("chrome-headless-shell") if p.is_file()]
        if len(binaries) != 1 or not binaries[0].resolve().is_relative_to(cache):
            raise Blocked(
                "Exact installed headless browser binary cannot be identified"
            )
        with binaries[0].open("rb") as stream:
            binary_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        result["browser_bytes"] = {
            "catalog_sha256": catalog_digest,
            "executable_sha256": binary_digest,
            "trust": (
                "Locked Playwright revision and vendor TLS download; "
                "native bytes captured for independent review"
            ),
        }
        stage = "standard_runner_docker_capability"
        docker = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            env=env,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if docker.returncode:
            raise Blocked(
                "Existing standard-runner Docker engine unavailable; "
                "no installation or privilege fallback"
            )
        result["docker_server_version"] = docker.stdout.decode().strip()
        run(
            "postgres_pull",
            ["docker", "pull", "--platform", "linux/amd64", PG_IMAGE],
            timeout=60,
        )
        image = json.loads(
            run("postgres_descriptor", ["docker", "image", "inspect", PG_IMAGE])
        )[0]
        pins = json.loads((ROOT / "bench/p0/pins.json").read_text())
        if (
            image["Architecture"] != "amd64"
            or image["Os"] != "linux"
            or image["Id"] != pins["postgres"]["config_digest"]
        ):
            raise Blocked("Pulled PostgreSQL architecture disagrees")
        result["postgres_image"] = {
            "reference": PG_IMAGE,
            "image_id": image["Id"],
            "architecture": image["Architecture"],
        }
        pg_env = PRIVATE / "postgres.env"
        pg_env.write_text(
            f"POSTGRES_USER=p0_bootstrap\nPOSTGRES_PASSWORD={admin_password}\n"
            "POSTGRES_DB=postgres\nPGDATA=/tmp/p0-data\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n"
        )
        pg_env.chmod(0o600)
        run(
            "postgres_start",
            [
                "docker",
                "run",
                "--detach",
                "--name",
                CONTAINER,
                "--platform",
                "linux/amd64",
                "--label",
                "finleak.p0.instance=" + instance_id,
                "--user",
                "postgres",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--shm-size",
                "128m",
                "--publish",
                "127.0.0.1:5432:5432",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=768m,mode=1777",
                "--tmpfs",
                "/var/run/postgresql:rw,nosuid,nodev,size=16m,mode=1777",
                "--env-file",
                str(pg_env),
                PG_IMAGE,
                "-c",
                "shared_buffers=64MB",
                "-c",
                "max_connections=20",
                "-c",
                "track_commit_timestamp=on",
                "-c",
                "log_statement=none",
                "-c",
                "log_min_error_statement=panic",
            ],
            timeout=15,
        )
        stage = "postgres_ready"
        for _ in range(80):
            code = subprocess.run(
                ["docker", "exec", CONTAINER, "pg_isready", "-U", "p0_bootstrap"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).returncode
            if code == 0:
                break
            time.sleep(0.25)
        else:
            raise Blocked("PostgreSQL did not become ready")
        sql = (
            f"CREATE ROLE finleak_p0 LOGIN PASSWORD '{db_password}' "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE;\n"
            f"CREATE ROLE p0_migrator LOGIN PASSWORD '{migration_password}' "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE;\n"
            f"CREATE DATABASE {DB_NAME} OWNER p0_migrator;\n"
        ).encode()
        run(
            "postgres_nonprivileged_database",
            [
                "docker",
                "exec",
                "-i",
                CONTAINER,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "p0_bootstrap",
                "-d",
                "postgres",
            ],
            input_=sql,
        )
        run(
            "migrations_0001_through_0010",
            [str(PYTHON), "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            timeout=45,
            extra_env={"FLA_DATABASE_URL": migration_url},
        )
        result["migration_0010"] = "APPLIED_SYNTHETIC_DATABASE_ONLY"
        provider = subprocess.Popen(
            [str(PYTHON), str(ROOT / "bench/p0/oidc_provider.py")],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        processes.append(provider)
        write(PRIVATE / "oidc.json", {"pid": provider.pid})
        ready("http://127.0.0.1:9100/.well-known/openid-configuration", 15)
        seed = json.loads(
            run(
                "synthetic_document_identity_fixture",
                [str(PYTHON), "-m", "acceptance.product_v11", "seed"],
                cwd=ROOT / "backend",
                timeout=20,
                extra_env={"FLA_DATABASE_URL": migration_url},
            )
        )
        if seed["status"] != "FIXTURE_ONLY" or seed["financial_records_inserted"] != 0:
            raise RuntimeError("Fixture did not satisfy source-only contract")
        run(
            "restrict_runtime_database_role",
            [
                "docker",
                "exec",
                "-i",
                CONTAINER,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "p0_bootstrap",
                "-d",
                DB_NAME,
            ],
            input_=(ROOT / "bench/p0/runtime-grants.sql").read_bytes(),
        )
        processes.append(backend_start(env))
        ready("http://127.0.0.1:8000/openapi.json", 20)
        front = subprocess.Popen(
            [
                "node",
                "node_modules/next/dist/bin/next",
                "dev",
                "--webpack",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            cwd=ROOT / "frontend",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        processes.append(front)
        write(PRIVATE / "frontend.json", {"pid": front.pid})
        ready("http://127.0.0.1:3000/login", 45)
        result["e2e_executed"] = True
        run(
            "browser_financial_acceptance",
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "--config",
                "playwright.p0.config.ts",
            ],
            cwd=ROOT / "frontend",
            timeout=150,
        )
        browser = json.loads((EVIDENCE / "browser.json").read_text())
        witness = json.loads((EVIDENCE / "witness.json").read_text())
        if (
            browser["status"] != "PASS"
            or browser["executed"] != 1
            or witness["status"] != "PASS"
        ):
            raise RuntimeError("Mandatory browser and PostgreSQL evidence missing")
        result.update(status="PASS", browser=browser, postgres_witness=witness)
        with urllib.request.urlopen(
            "http://127.0.0.1:9100/receipts", timeout=3
        ) as response:
            receipt = json.load(response)
        assert receipt["counts"]["authenticated_grants"] >= 3
        assert receipt["counts"]["jwks"] >= 1
        result["oidc"] = receipt
    except SeedFailure as error:
        result.update(
            status=error.status,
            stage=SEED_STAGE,
            reason=error.diagnostic["reason_code"],
            fixture_diagnostic=error.diagnostic,
            e2e_executed=False,
        )
    except Blocked as error:
        result.update(status="BLOCKED", stage=stage, reason=str(error))
    except subprocess.TimeoutExpired:
        result.update(
            status="BLOCKED", stage=stage, reason="Stage exceeded its bounded deadline"
        )
    except (
        AssertionError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        result.update(status="FAIL", stage=stage, reason=type(error).__name__)
    finally:
        for process in processes:
            if process.poll() is not None:
                process.wait()
        try:
            if owns_resources:
                cleanup()
                result["cleanup"] = "COMPLETED"
            else:
                result["cleanup"] = "NOT_STARTED"
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            result["cleanup"] = "FAILED_OR_INTERRUPTED"
            result["status"] = "FAIL"
        try:
            validate_result_diagnostic(result)
        except (ValueError, TypeError):
            result.update(
                status="FAIL",
                e2e_executed=False,
                reason="DIAGNOSTIC_UNAVAILABLE",
                fixture_diagnostic=public_diagnostic(
                    None, "UNAVAILABLE", "DIAGNOSTIC_UNAVAILABLE", "fixture_process"
                ),
            )
        write(EVIDENCE / "result.json", result)
        payload = (EVIDENCE / "result.json").read_bytes()
        print("FINLEAK_P0_RESULT_SHA256=" + hashlib.sha256(payload).hexdigest())
        print("FINLEAK_P0_RESULT_BASE64=" + base64.b64encode(payload).decode())
        print("FINLEAK P0 development result: " + result["status"])
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["status"]]


if __name__ == "__main__":
    if sys.argv[1:] == ["restart-backend"]:
        restart_backend()
    elif sys.argv[1:] == ["run"]:
        raise SystemExit(execute())
    elif sys.argv[1:] == ["cleanup"]:
        if PRIVATE.exists():
            execution_gate(ROOT)
            cleanup()
        print("P0 scoped cleanup complete; no external resource operation")
    else:
        raise SystemExit(
            "Use run or restart-backend only after separate manual-job authorization"
        )
