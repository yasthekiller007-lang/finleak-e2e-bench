"""Private, bounded exact-byte ClamD INSTREAM; never a public scan service."""

import re
import socket
import stat
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import ip_address
from time import monotonic


class ScannerFailure(OSError):
    def __init__(self, code="scanner_unavailable"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ScanVerdict:
    status: str
    profile: str = "private-clamav/1"
    version: str | None = None


class UnconfiguredScanner:
    def healthcheck(self):
        raise ScannerFailure("scanner_not_configured")

    def scan(self, source, *, max_bytes, deadline):
        return ScanVerdict("UNAVAILABLE")


class ClamAVScanner:
    def __init__(self, *, socket_path=None, host=None, port=3310, timeout_seconds=5):
        if socket_path is not None:
            from pathlib import Path

            if not Path(socket_path).is_absolute() or ".." in Path(socket_path).parts:
                raise ScannerFailure("private_scanner_socket_required")
            socket_path = str(socket_path)
        elif host is not None:
            try:
                if not ip_address(host).is_loopback or ":" in host:
                    raise ValueError()
            except ValueError:
                raise ScannerFailure("private_scanner_socket_required") from None
        self.socket_path, self.host, self.port = socket_path, host, port
        self.timeout_seconds = timeout_seconds

    def remaining(self, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError()
        return min(self.timeout_seconds, remaining)

    @contextmanager
    def connection(self, deadline):
        if self.socket_path:
            from pathlib import Path

            path = Path(self.socket_path)
            socket_state, parent_state = path.lstat(), path.parent.lstat()
            if (
                not stat.S_ISSOCK(socket_state.st_mode)
                or not stat.S_ISDIR(parent_state.st_mode)
                or socket_state.st_mode & 0o007
                or parent_state.st_mode & 0o027
            ):
                raise ScannerFailure("private_scanner_socket_permissions_required")
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        elif self.host:
            # Engineering protocol fixtures only. Production uses a private local socket.
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            raise ScannerFailure("scanner_not_configured")
        try:
            connection.settimeout(self.remaining(deadline))
            connection.connect(self.socket_path or (self.host, self.port))
            yield connection
        finally:
            connection.close()

    def send(self, connection, value, deadline):
        connection.settimeout(self.remaining(deadline))
        connection.sendall(value)

    def response(self, connection, deadline):
        output = bytearray()
        while b"\0" not in output:
            connection.settimeout(self.remaining(deadline))
            chunk = connection.recv(257 - len(output))
            if not chunk:
                raise ScannerFailure("scanner_protocol_unavailable")
            output.extend(chunk)
            if len(output) > 256:
                raise ScannerFailure("scanner_response_limit")
        if not output.endswith(b"\0") or output.count(b"\0") != 1:
            raise ScannerFailure("scanner_protocol_unavailable")
        return bytes(output[:-1])

    def version(self, deadline):
        with self.connection(deadline) as connection:
            self.send(connection, b"zVERSION\0", deadline)
            value = self.response(connection, deadline)
        match = re.fullmatch(
            rb"ClamAV (1\.(?:4|5)\.\d+)/(\d{1,10})/"
            rb"[A-Za-z]{3} [A-Za-z]{3} [ 0-9]{2} [0-9:]{8} [0-9]{4}",
            value,
        )
        if not match:
            raise ScannerFailure("scanner_version_unqualified")
        parts = tuple(map(int, match[1].split(b".")))
        if parts < ((1, 4, 6) if parts[1] == 4 else (1, 5, 4)):
            raise ScannerFailure("scanner_version_unqualified")
        # Do not persist the server's arbitrary response, dates, signatures or diagnostics.
        return "clamav/" + match[1].decode() + ";database/" + match[2].decode()

    def healthcheck(self):
        try:
            return self.version(monotonic() + self.timeout_seconds)
        except (OSError, ValueError):
            raise ScannerFailure() from None

    def scan(self, source, *, max_bytes, deadline):
        version = None
        try:
            version = self.version(deadline)
            total = 0
            with self.connection(deadline) as connection:
                self.send(connection, b"zINSTREAM\0", deadline)
                while chunk := source.read(32 * 1024):
                    self.remaining(deadline)
                    total += len(chunk)
                    if total > max_bytes:
                        return ScanVerdict("SUSPICIOUS", version=version)
                    self.send(connection, struct.pack("!I", len(chunk)) + chunk, deadline)
                self.send(connection, b"\0\0\0\0", deadline)
                value = self.response(connection, deadline)
            if value == b"stream: OK":
                return ScanVerdict("CLEAN", version=version)
            if re.fullmatch(rb"stream: [A-Za-z0-9_.()-]{1,180} FOUND", value):
                status = "SUSPICIOUS" if b"Heuristics." in value else "INFECTED"
                return ScanVerdict(status, version=version)
            return ScanVerdict("UNKNOWN", version=version)
        except TimeoutError:
            return ScanVerdict("TIMEOUT", version=version)
        except (OSError, ValueError):
            return ScanVerdict("UNAVAILABLE", version=version)


def build_scanner(settings):
    if settings.scanner_backend != "clamav":
        return UnconfiguredScanner()
    if settings.environment == "production" and not settings.scanner_socket_path:
        raise ScannerFailure("private_scanner_socket_required")
    return ClamAVScanner(
        socket_path=settings.scanner_socket_path,
        host=settings.scanner_host,
        port=settings.scanner_port,
        timeout_seconds=settings.scanner_timeout_seconds,
    )
