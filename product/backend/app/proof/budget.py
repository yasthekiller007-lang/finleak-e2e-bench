import hashlib
import time
from dataclasses import dataclass, field

from app.proof.schema import OperationalLimits


class ProofError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)


@dataclass
class Budget:
    limits: OperationalLimits
    started: float = field(default_factory=time.monotonic)
    bytes_read: int = 0

    def check(self):
        if time.monotonic() - self.started >= self.limits.work_seconds:
            raise ProofError("proof_work_budget", "Proof work budget exceeded", 503)

    def bound(self, value: int, name: str):
        self.check()
        if value > getattr(self.limits, name):
            raise ProofError("proof_resource_limit", f"Proof exceeds the {name} limit", 413)

    def read(self, size: int):
        self.bytes_read += size
        self.bound(self.bytes_read, "source_bytes")


def verify_source(storage, document, budget: Budget, *, capture: bool = False):
    """Hash bounded actual bytes, never just Document.sha256. No unverified streaming."""
    hasher = hashlib.sha256()
    total = 0
    output = bytearray() if capture else None
    budget.check()
    try:
        with storage.open(document.storage_key) as stream:
            while chunk := stream.read(64 * 1024):
                budget.read(len(chunk))
                total += len(chunk)
                hasher.update(chunk)
                if output is not None:
                    output.extend(chunk)
    except FileNotFoundError:
        return "UNAVAILABLE", None
    except (OSError, ValueError):
        return "UNAVAILABLE", None
    budget.check()
    if total != document.file_size or hasher.hexdigest() != document.sha256:
        return "MISMATCH", None
    return "AVAILABLE_VERIFIED", bytes(output) if output is not None else None
