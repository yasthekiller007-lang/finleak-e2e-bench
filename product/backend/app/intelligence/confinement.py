"""Child-only Linux parser confinement; unavailable protection fails closed.

Landlock ABI >=3 fences file reads to code/runtime and the exact private source.
A seccomp default-deny profile admits only inert, single-process Python parsing.
Never call confine() in the API process. No credentials or data directories are
allowed, no network/process/exec/io_uring syscalls are admitted, and source bytes
cannot be modified. Existing stdin/stdout are the only retained capabilities.
"""

import ctypes
import errno
import os
import platform
import sysconfig
from pathlib import Path

PROFILE = "linux-parser/1"
LANDLOCK_CALLS = (444, 445, 446)  # Linux x86_64 and generic aarch64 syscall tables.
READ_FILE = 1 << 2
READ_DIR = 1 << 3
HANDLED_FS = (1 << 15) - 1  # ABI 3: includes REFER and TRUNCATE.
# Default ERRNO(EPERM), including future/unknown syscalls. File writes remain
# prohibited by Landlock even when openat/write are used for retained stdout.
SYSCALLS = (
    "read",
    "write",
    "readv",
    "writev",
    "pread64",
    "pwrite64",
    "close",
    "close_range",
    "lseek",
    "fstat",
    "newfstatat",
    "stat",
    "lstat",
    "statx",
    "open",
    "openat",
    "getdents",
    "getdents64",
    "readlink",
    "readlinkat",
    "access",
    "faccessat",
    "faccessat2",
    "getcwd",
    "mmap",
    "mmap2",
    "mprotect",
    "munmap",
    "mremap",
    "brk",
    "madvise",
    "futex",
    "futex_time64",
    "clock_gettime",
    "clock_gettime64",
    "gettimeofday",
    "time",
    "nanosleep",
    "clock_nanosleep",
    "clock_nanosleep_time64",
    "getpid",
    "gettid",
    "getppid",
    "getuid",
    "geteuid",
    "getgid",
    "getegid",
    "getrandom",
    "rt_sigaction",
    "rt_sigprocmask",
    "rt_sigreturn",
    "sigaltstack",
    "prlimit64",
    "getrlimit",
    "setrlimit",
    "exit",
    "exit_group",
    "uname",
    "sched_yield",
    "sched_getaffinity",
    "fcntl",
    "fcntl64",
    "dup",
    "dup2",
    "dup3",
    "select",
    "pselect6",
    "poll",
    "ppoll",
    "restart_syscall",
    "rseq",
)


class ConfinementUnavailable(OSError):
    pass


class Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _libc():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise ConfinementUnavailable("parser_confinement_unavailable")
    return ctypes.CDLL(None, use_errno=True)


def available():
    """Read-only kernel/library probe. Successful installation is tested in a child."""
    try:
        libc = _libc()
        if libc.syscall(LANDLOCK_CALLS[0], 0, 0, 1) < 3:
            return False
        ctypes.CDLL("libseccomp.so.2", use_errno=True)
        return True
    except OSError:
        return False


def _read_paths(source):
    paths = {Path(__file__).resolve().parents[1], Path(source).resolve(strict=True)}
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        paths.add(Path(sysconfig.get_path(key)).resolve(strict=True))
    triple = "x86_64-linux-gnu" if platform.machine() == "x86_64" else "aarch64-linux-gnu"
    for root in ("/lib", "/usr/lib"):
        candidate = Path(root) / triple
        if candidate.is_dir():
            paths.add(candidate.resolve(strict=True))
        # Musl distributions use flat immutable system-library paths. Admit exact
        # shared-library files only, never their parent/data/config directories.
        for file in Path(root).glob("*.so*"):
            if file.is_file():
                paths.add(file.resolve(strict=True))
    # No project root, HOME, /proc, /etc, /tmp or source-parent directory rule.
    return paths


def confine(source):
    libc = _libc()
    if libc.syscall(LANDLOCK_CALLS[0], 0, 0, 1) < 3:
        raise ConfinementUnavailable("parser_confinement_unavailable")
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
        seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
        seccomp.seccomp_init.restype = ctypes.c_void_p
        seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
        seccomp.seccomp_rule_add.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
        seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
        # No added alternate architecture: libseccomp kills bad-architecture calls.
        context = seccomp.seccomp_init(0x00050000 | errno.EPERM)
        if not context:
            raise ConfinementUnavailable("parser_confinement_unavailable")
        try:
            for name in SYSCALLS:
                number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
                if number >= 0 and seccomp.seccomp_rule_add(context, 0x7FFF0000, number, 0):
                    raise ConfinementUnavailable("parser_confinement_unavailable")
            if libc.prctl(38, 1, 0, 0, 0):  # PR_SET_NO_NEW_PRIVS
                raise ConfinementUnavailable("parser_confinement_unavailable")
            rule = Ruleset(HANDLED_FS)
            fd = libc.syscall(LANDLOCK_CALLS[0], ctypes.byref(rule), ctypes.sizeof(rule), 0)
            if fd < 0:
                raise ConfinementUnavailable("parser_confinement_unavailable")
            try:
                for path in _read_paths(source):
                    path_fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                    try:
                        allowed = READ_FILE | (READ_DIR if path.is_dir() else 0)
                        entry = PathRule(allowed, path_fd)
                        if libc.syscall(LANDLOCK_CALLS[1], fd, 1, ctypes.byref(entry), 0):
                            raise ConfinementUnavailable("parser_confinement_unavailable")
                    finally:
                        os.close(path_fd)
                if libc.syscall(LANDLOCK_CALLS[2], fd, 0):
                    raise ConfinementUnavailable("parser_confinement_unavailable")
            finally:
                os.close(fd)
            if seccomp.seccomp_load(context):
                raise ConfinementUnavailable("parser_confinement_unavailable")
        finally:
            seccomp.seccomp_release(context)
    except OSError:
        raise ConfinementUnavailable("parser_confinement_unavailable") from None


def healthcheck():
    """Bounded child proves actual installation; no untrusted input is parsed."""
    import json
    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.intelligence.confinement_probe"],
            capture_output=True,
            timeout=5,
            cwd=Path(__file__).resolve().parents[2],
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        if result.returncode or len(result.stdout) > 256:
            raise ConfinementUnavailable("parser_confinement_unavailable")
        if json.loads(result.stdout) != {"status": "protected", "denied": 3}:
            raise ConfinementUnavailable("parser_confinement_unavailable")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ConfinementUnavailable("parser_confinement_unavailable") from None
