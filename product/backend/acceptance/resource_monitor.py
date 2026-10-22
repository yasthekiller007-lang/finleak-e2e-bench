"""Read-only sampling of disposable acceptance workers, storage and PG pressure."""

import json
import os
import signal
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from acceptance.browser_runtime import DIRECTORY, guard


def byte_size(paths):
    total = 0
    for path in paths:
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            # Parser cleanup can unlink a file between enumeration and stat.
            continue
    return total


def main():
    guard()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    engine = create_engine(os.environ["FLA_DATABASE_URL"], hide_parameters=True)
    samples = []
    try:
        while running:
            processes = {}
            for path in Path("/proc").iterdir():
                if not path.name.isdigit():
                    continue
                try:
                    stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
                    cmd = (path / "cmdline").read_bytes()
                    processes[int(path.name)] = (int(stat[1]), cmd, stat)
                except (OSError, ValueError, IndexError):
                    continue
            pids = {
                pid
                for pid, (_, cmd, _) in processes.items()
                if b"uvicorn" in cmd and b"acceptance.browser_runtime:application" in cmd
            }
            while True:
                children = {pid for pid, (parent, _, _) in processes.items() if parent in pids}
                new = children - pids
                if not new:
                    break
                pids.update(new)
            rss = sum(int(processes[p][2][21]) for p in pids) * os.sysconf("SC_PAGE_SIZE")
            cpu = sum(int(processes[p][2][11]) + int(processes[p][2][12]) for p in pids)
            with engine.connect() as connection:
                activity = connection.execute(
                    text(
                        "SELECT count(*), count(*) FILTER (WHERE wait_event_type='Lock') "
                        "FROM pg_stat_activity WHERE datname=current_database()"
                    )
                ).one()
            original_bytes = byte_size((DIRECTORY / "originals").rglob("*"))
            parser_temp_bytes = sum(
                byte_size(directory.rglob("*"))
                for directory in Path(tempfile.gettempdir()).glob("fla-extraction-*")
                if directory.is_dir() and not directory.is_symlink()
            )
            samples.append(
                {
                    "elapsed_seconds": round(time.monotonic(), 3),
                    "backend_processes": len(pids),
                    "backend_rss_bytes": rss,
                    "backend_cpu_seconds": cpu / os.sysconf("SC_CLK_TCK"),
                    "original_bytes": original_bytes,
                    "parser_temp_bytes": parser_temp_bytes,
                    "original_and_temp_bytes": original_bytes + parser_temp_bytes,
                    "db_connections": activity[0],
                    "db_lock_waiters": activity[1],
                }
            )
            time.sleep(0.5)
    finally:
        with engine.connect() as connection:
            metadata = {
                "postgres": connection.scalar(text("SHOW server_version")),
                "schema": connection.scalar(text("SELECT version_num FROM alembic_version")),
                "commit_tracking": connection.scalar(text("SHOW track_commit_timestamp")),
            }
        engine.dispose()
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        (DIRECTORY / "resources.json").write_text(
            json.dumps(
                {
                    "release_sha": os.environ["RELEASE_SHA"],
                    "date": datetime.now(UTC).isoformat(),
                    "tester": "GitHub Actions synthetic acceptance",
                    "sampling_seconds": 0.5,
                    "scope": "API process tree; dedicated database connections include observer",
                    "metadata": metadata,
                    "samples": samples,
                    "limits": "Sampling may miss peaks; no cloud IO/WAL/disk capacity claim",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
