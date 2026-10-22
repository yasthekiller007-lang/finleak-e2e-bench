"""Domain-separated, versioned canonical JSON. Financial values stay exact strings."""

import hashlib
import json
import re
from typing import Any

SCHEMA = "proof-manifest/1"
ASSEMBLY = "proof-assembly/1"
DISCLOSURE = "proof-disclosure/1"
DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


class CanonicalError(ValueError):
    pass


def quoted(value: str) -> str:
    result = ['"']
    for char in value:
        code = ord(char)
        if 0xD800 <= code <= 0xDFFF:
            raise CanonicalError("Invalid Unicode scalar")
        if code < 32:
            result.append(f"\\u{code:04x}")
        elif char in {'"', "\\"}:
            result.append("\\" + char)
        else:
            result.append(char)
    result.append('"')
    return "".join(result)


def canonical(value: Any) -> bytes:
    def encode(item):
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, str):
            return quoted(item)
        if type(item) is int:
            return str(item)
        if isinstance(item, list | tuple):
            return "[" + ",".join(encode(x) for x in item) + "]"
        if isinstance(item, dict) and all(isinstance(k, str) for k in item):
            return "{" + ",".join(quoted(k) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        raise CanonicalError("Unsupported canonical value")

    return encode(value).encode("utf-8")


def digest(domain: str, value: Any) -> str:
    return hashlib.sha256((domain + "\n").encode("ascii") + canonical(value)).hexdigest()


def fingerprint(core: dict) -> str:
    return digest("FLA-PROOF-MANIFEST/1", core)


def snapshot_digest(snapshot: dict) -> str:
    # Deliberately preserves every array's original order, scale, timestamp and null.
    return digest("FLA-EVALUATION-SNAPSHOT/1", snapshot)


def strict_loads(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CanonicalError("Duplicate JSON key")
            result[key] = value
        return result

    def unsupported(_):
        raise CanonicalError("Unsupported numeric token")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=unsupported,
            parse_constant=unsupported,
        )
        canonical(value)  # Includes scalar validity throughout the entire tree.
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CanonicalError("Invalid canonical JSON input") from exc


def leaves(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            result.update(leaves(child, path + "/" + escaped))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(leaves(child, path + "/" + str(index)))
        return result
    return {path: value}
