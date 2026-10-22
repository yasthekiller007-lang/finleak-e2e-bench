import hashlib
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest

from app.modules.storage import LocalObjectStorage
from app.proof.budget import Budget, ProofError, verify_source
from app.proof.canonical import CanonicalError, canonical, digest, fingerprint, strict_loads
from app.proof.schema import OperationalLimits


def test_independent_canonical_unicode_control_and_exact_scale_vector():
    data = {
        "é": "e\u0301",
        "z": '"\\/\n\t\x00',
        "a": [None, False, True, 7, "18.40"],
        "😀": "\u2028\u2029",
    }
    expected = (
        b'{"a":[null,false,true,7,"18.40"],"z":"\\"\\\\/\\u000a\\u0009\\u0000",'
        + '"é":"é","😀":"\u2028\u2029"}'.encode()
    )
    assert canonical(data) == expected
    assert fingerprint(data) == hashlib.sha256(b"FLA-PROOF-MANIFEST/1\n" + expected).hexdigest()
    assert canonical({"a": "18.40"}) != canonical({"a": "18.4"})
    assert canonical({"a": "é"}) != canonical({"a": "é"})
    assert digest("FLA-EVALUATION-SNAPSHOT/1", ["a", "b"]) != digest(
        "FLA-EVALUATION-SNAPSHOT/1", ["b", "a"]
    )
    assert digest("FLA-EVALUATION-SNAPSHOT/1", data) != fingerprint(data)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":{"b":1,"b":1}}',
        b'{"v":1.0}',
        b'{"v":1e3}',
        b'{"v":NaN}',
        b'{"v":Infinity}',
        b'{"v":"\\ud800"}',
        b"\xef\xbb\xbf{}",
    ],
)
def test_strict_json_rejects_ambiguous_numbers_keys_and_scalars(raw):
    with pytest.raises(CanonicalError):
        strict_loads(raw)


@pytest.mark.parametrize("value", [1.0, float("nan"), Decimal("1.0"), {1: "a"}, "\udfff"])
def test_canonical_rejects_unsupported_values(value):
    with pytest.raises(CanonicalError):
        canonical(value)


def test_actual_source_bytes_mismatch_missing_and_cumulative_limit(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    stored = storage.put("org/doc/source", BytesIO(b"source"), max_bytes=100)
    doc = SimpleNamespace(storage_key=stored.key, sha256=stored.sha256, file_size=stored.file_size)
    budget = Budget(OperationalLimits(source_bytes=12))
    assert verify_source(storage, doc, budget, capture=True) == ("AVAILABLE_VERIFIED", b"source")
    assert verify_source(storage, doc, budget)[0] == "AVAILABLE_VERIFIED"
    with pytest.raises(ProofError, match="proof_resource_limit"):
        verify_source(storage, doc, budget)
    (tmp_path / stored.key).write_bytes(b"tamper")
    assert verify_source(storage, doc, Budget(OperationalLimits())) == ("MISMATCH", None)
    storage.delete(stored.key)
    assert verify_source(storage, doc, Budget(OperationalLimits())) == ("UNAVAILABLE", None)


def test_nonregular_source_cannot_block_work_budget(tmp_path):
    import os

    storage = LocalObjectStorage(tmp_path)
    os.mkfifo(tmp_path / "fifo")
    with pytest.raises(ValueError, match="regular"):
        storage.open("fifo")


def test_work_budget_returns_explicit_failure():
    budget = Budget(OperationalLimits(), started=0)
    with pytest.raises(ProofError, match="proof_work_budget"):
        budget.check()


def test_source_changed_during_capture_never_returns_mixed_bytes():
    original = b"a" * 65536 + b"b" * 65536

    class RacingStream(BytesIO):
        def read(self, size=-1):
            result = super().read(size)
            if self.tell() == 65536:
                self.write(b"c" * 65536)
                self.seek(65536)
            return result

    storage = SimpleNamespace(open=lambda key: RacingStream(original))
    doc = SimpleNamespace(
        storage_key="private", file_size=len(original), sha256=hashlib.sha256(original).hexdigest()
    )
    assert verify_source(storage, doc, Budget(OperationalLimits()), capture=True) == (
        "MISMATCH",
        None,
    )


def test_redaction_includes_export_metadata_and_never_mutates_canonical_core():
    from app.proof.service import redaction_filter

    secret = "00000000-0000-4000-8000-000000000001"
    package = SimpleNamespace(
        core={
            "authority": {"actor_id": secret},
            "source": "Reviewer " + secret,
            "sources": [{"sha256": "a" * 64}],
            "diagnostic": hashlib.sha256(secret.encode()).hexdigest(),
        }
    )
    proposal = SimpleNamespace(detail={"paths": ["/authority/actor_id"]})
    mask, verify = redaction_filter(package, proposal)
    exported = mask({"content": package.core, "export_context": {"actor_id": secret}})
    verify(exported)
    assert secret not in canonical(exported).decode()
    assert "a" * 64 not in canonical(exported).decode()
    assert hashlib.sha256(secret.encode()).hexdigest() not in canonical(exported).decode()
    assert package.core["authority"]["actor_id"] == secret
    with pytest.raises(ProofError, match="proof_redaction_leak"):
        verify({"export_context": {"actor_id": secret}})


def test_partial_quote_values_and_unlabelled_hashes_do_not_escape_redaction():
    from app.proof.service import redaction_filter

    package = SimpleNamespace(
        core={
            "quote": "Private bank IBAN-SECRET-12345",
            "raw_candidate": "IBAN-SECRET-12345",
            "summary": "private BANK iban-secret-12345",
            "diagnostic": "b" * 64,
        }
    )
    proposal = SimpleNamespace(detail={"paths": ["/quote"]})
    mask, verify = redaction_filter(package, proposal)
    content = mask(package.core)
    verify(content)
    assert "IBAN-SECRET-12345" not in canonical(content).decode()
    assert "b" * 64 not in canonical(content).decode()
