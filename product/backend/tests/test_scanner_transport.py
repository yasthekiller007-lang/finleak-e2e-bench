"""Actual private socket/protocol tests; these do not claim malware-engine qualification."""

import io
import os
import socketserver
import struct
import tempfile
from contextlib import contextmanager
from threading import Event, Thread
from time import monotonic

import pytest

from app.core.config import Settings
from app.modules.scanner import (
    ClamAVScanner,
    ScannerFailure,
    UnconfiguredScanner,
    build_scanner,
)


@contextmanager
def scanner_server(
    tmp_path,
    *,
    reply=b"stream: OK\0",
    version=b"ClamAV 1.4.6/28000/Sun Oct  4 01:00:00 2026\0",
    stall=False,
    unix=False,
):
    received = []
    done = Event()

    class Handler(socketserver.BaseRequestHandler):
        def exact(self, length):
            value = bytearray()
            while len(value) < length:
                chunk = self.request.recv(length - len(value))
                if not chunk:
                    return None
                value.extend(chunk)
            return bytes(value)

        def handle(self):
            self.request.settimeout(1)
            command = bytearray()
            while len(command) < 32 and not command.endswith(b"\0"):
                value = self.exact(1)
                if value is None:
                    return
                command.extend(value)
            if command == b"zVERSION\0":
                self.request.sendall(version)
            elif command == b"zINSTREAM\0":
                source = bytearray()
                while True:
                    prefix = self.exact(4)
                    if prefix is None:
                        return
                    length = struct.unpack("!I", prefix)[0]
                    if length == 0:
                        break
                    chunk = self.exact(length)
                    if chunk is None:
                        return
                    source.extend(chunk)
                received.append(bytes(source))
                if stall:
                    done.wait(2)
                    return
                self.request.sendall(reply)

    class Server(
        socketserver.ThreadingUnixStreamServer if unix else socketserver.ThreadingTCPServer
    ):
        daemon_threads = True

    with tempfile.TemporaryDirectory(prefix="fla-scan-test-") as private:
        path = private + "/clamd.sock"
        try:
            server = Server(path if unix else ("127.0.0.1", 0), Handler)
        except PermissionError:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                raise
            pytest.skip(
                "Work's sandbox forbids private Unix sockets; required CI tests the real socket"
            )
        with server:
            if unix:
                os.chmod(path, 0o600)
            worker = Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
            )
            worker.start()
            try:
                scanner = (
                    ClamAVScanner(socket_path=path, timeout_seconds=0.05)
                    if unix
                    else ClamAVScanner(
                        host="127.0.0.1", port=server.server_address[1], timeout_seconds=0.05
                    )
                )
                yield scanner, received
            finally:
                done.set()
                server.shutdown()
                worker.join(2)


def test_clean_protocol_streams_exact_original_and_records_only_qualified_version(tmp_path):
    original = b"field,value\r\nreference,SYNTHETIC\r\n" + bytes(range(256)) * 300
    with scanner_server(tmp_path) as (scanner, received):
        assert scanner.healthcheck() == "clamav/1.4.6;database/28000"
        result = scanner.scan(
            io.BytesIO(original), max_bytes=len(original), deadline=monotonic() + 1
        )
    assert result.status == "CLEAN"
    assert result.version == "clamav/1.4.6;database/28000"
    assert received == [original]


def test_production_private_unix_transport_streams_actual_source_bytes(tmp_path):
    with scanner_server(tmp_path, unix=True) as (scanner, received):
        result = scanner.scan(
            io.BytesIO(b"Synthetic private source"), max_bytes=100, deadline=monotonic() + 1
        )
    assert result.status == "CLEAN" and received == [b"Synthetic private source"]


@pytest.mark.parametrize(
    "reply,status",
    [
        (b"stream: Win.Test.EICAR_HDB-1 FOUND\0", "INFECTED"),
        (b"stream: Heuristics.Limits.Exceeded.MaxSize FOUND\0", "SUSPICIOUS"),
        (b"stream: PRIVATE-FILENAME ERROR\0", "UNKNOWN"),
        (b"stream: OKISH\0", "UNKNOWN"),
        (b"stream: OK\0stream: OK\0", "UNAVAILABLE"),
        (b"stream: OK\n", "UNAVAILABLE"),
        (b"stream: " + b"x" * 260 + b"\0", "UNAVAILABLE"),
    ],
)
def test_nonclean_malformed_and_resource_verdicts_never_release_or_leak_diagnostics(
    tmp_path, reply, status
):
    with scanner_server(tmp_path, reply=reply) as (scanner, _):
        result = scanner.scan(
            io.BytesIO(b"Synthetic data"), max_bytes=100, deadline=monotonic() + 1
        )
    assert result.status == status
    assert "PRIVATE-FILENAME" not in repr(result)
    assert result.status != "CLEAN"


@pytest.mark.parametrize(
    "version",
    [
        b"ClamAV 1.4.5/28000/Sun Oct  4 01:00:00 2026\0",
        b"ClamAV 1.5.3/28000/Sun Oct  4 01:00:00 2026\0",
        b"ClamAV 2.0.0/28000/Sun Oct  4 01:00:00 2026\0",
        b"ClamAV 1.4.6/28000/private-sensitive-path\0",
        b"INVALID\0",
    ],
)
def test_unqualified_or_unknown_engine_version_fails_closed(tmp_path, version):
    with scanner_server(tmp_path, version=version) as (scanner, received):
        result = scanner.scan(io.BytesIO(b"Synthetic"), max_bytes=20, deadline=monotonic() + 1)
    assert result.status == "UNAVAILABLE" and result.version is None
    assert not received


def test_private_scanner_outage_timeout_and_expired_budget_are_distinct_closed_results(tmp_path):
    missing = ClamAVScanner(host="127.0.0.1", port=1)
    assert (
        missing.scan(io.BytesIO(b"Synthetic"), max_bytes=20, deadline=monotonic() + 1).status
        == "UNAVAILABLE"
    )
    with scanner_server(tmp_path, stall=True) as (scanner, _):
        assert (
            scanner.scan(io.BytesIO(b"Synthetic"), max_bytes=20, deadline=monotonic() + 1).status
            == "TIMEOUT"
        )
    assert (
        missing.scan(io.BytesIO(b"Synthetic"), max_bytes=20, deadline=monotonic() - 1).status
        == "TIMEOUT"
    )


def test_actual_input_size_bound_never_becomes_clean(tmp_path):
    with scanner_server(tmp_path) as (scanner, _):
        result = scanner.scan(io.BytesIO(b"123456"), max_bytes=5, deadline=monotonic() + 1)
    assert result.status == "SUSPICIOUS"


@pytest.mark.parametrize("host", ["scanner.example.test", "10.1.2.3", "8.8.8.8"])
def test_network_configuration_cannot_turn_into_a_public_scan_service(host):
    with pytest.raises(ScannerFailure, match="private_scanner_socket_required"):
        ClamAVScanner(host=host)


def test_production_requires_private_local_socket_and_no_unconfigured_fallback(tmp_path):
    settings = Settings(
        _env_file=None, environment="production", scanner_backend="clamav", scanner_host="127.0.0.1"
    )
    with pytest.raises(ScannerFailure, match="private_scanner_socket_required"):
        build_scanner(settings)
    settings.scanner_socket_path = tmp_path / "scanner.sock"
    assert isinstance(build_scanner(settings), ClamAVScanner)
    assert isinstance(build_scanner(Settings(_env_file=None)), UnconfiguredScanner)
    with pytest.raises(ScannerFailure, match="scanner_not_configured"):
        UnconfiguredScanner().healthcheck()


@pytest.mark.parametrize("unsafe", ["socket", "directory"])
def test_private_unix_transport_rejects_world_accessible_socket_or_parent(tmp_path, unsafe):
    from pathlib import Path

    with scanner_server(tmp_path, unix=True) as (scanner, received):
        target = (
            Path(scanner.socket_path) if unsafe == "socket" else Path(scanner.socket_path).parent
        )
        original = target.stat().st_mode & 0o777
        try:
            os.chmod(target, 0o666 if unsafe == "socket" else 0o755)
            verdict = scanner.scan(
                io.BytesIO(b"Synthetic"), max_bytes=100, deadline=monotonic() + 1
            )
            assert verdict.status == "UNAVAILABLE" and received == []
        finally:
            os.chmod(target, original)
