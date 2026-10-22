import base64
import hashlib
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import Settings
from app.modules.s3_storage import BoundedRemoteReader, S3ObjectStorage, StorageFailure
from app.modules.storage import LocalObjectStorage, build_storage, document_storage_key
from app.proof.budget import Budget, verify_source
from app.proof.schema import OperationalLimits


def failure(code, status=503):
    return ClientError(
        {
            "Error": {"Code": code, "Message": "customer-secret"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "Synthetic",
    )


class PrivateS3Fixture:
    """A unit fixture, never presented as a provider privacy/conformance result."""

    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()
        self.versioning = "Enabled"
        self.encrypted = True
        self.public = False
        self.policy = None
        self.owner = "synthetic-owner"
        self.grantee = self.owner
        self.outage = False
        self.puts = []

    def put_object(self, **values):
        self.puts.append(values)
        assert values["IfNoneMatch"] == "*"
        assert values["ServerSideEncryption"] == "AES256"
        content = values["Body"].read()
        assert len(content) == values["ContentLength"]
        assert (
            base64.b64encode(hashlib.sha256(content).digest()).decode() == values["ChecksumSHA256"]
        )
        with self.lock:
            if values["Key"] in self.values:
                raise failure("PreconditionFailed", 412)
            self.values[values["Key"]] = content
        return {"ServerSideEncryption": "AES256", "VersionId": "original-version"}

    def get_object(self, **values):
        if self.outage:
            raise EndpointConnectionError(endpoint_url="https://credential-hidden.example.test")
        if values["Key"] not in self.values:
            raise failure("NoSuchKey", 404)
        content = self.values[values["Key"]]
        return {
            "Body": io.BytesIO(content),
            "ContentLength": len(content),
            "ServerSideEncryption": "AES256",
        }

    def delete_object(self, **values):
        self.values.pop(values["Key"], None)
        return {}

    def get_bucket_versioning(self, **values):
        return {"Status": self.versioning}

    def get_bucket_encryption(self, **values):
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
                if self.encrypted
                else []
            }
        }

    def get_public_access_block(self, **values):
        return {
            "PublicAccessBlockConfiguration": {
                n: not self.public
                for n in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            }
        }

    def get_bucket_acl(self, **values):
        return {
            "Owner": {"ID": self.owner},
            "Grants": [
                {
                    "Grantee": {"Type": "CanonicalUser", "ID": self.grantee},
                    "Permission": "FULL_CONTROL",
                }
            ],
        }

    def get_bucket_policy(self, **values):
        if self.policy is None:
            raise failure("NoSuchBucketPolicy", 404)
        return {"Policy": self.policy}


def settings(**values):
    return Settings(
        _env_file=None,
        environment="test",
        storage_backend="s3",
        s3_endpoint_url="http://127.0.0.1:9000",
        s3_bucket="synthetic-originals",
        s3_region="synthetic-region",
        **values,
    )


@pytest.fixture(params=["local", "s3-unit-fixture"])
def storage(request, tmp_path):
    return (
        LocalObjectStorage(tmp_path)
        if request.param == "local"
        else S3ObjectStorage(settings(), client=PrivateS3Fixture())
    )


def test_shared_storage_exact_bytes_size_checksum_and_no_overwrite(storage):
    key = document_storage_key(uuid4(), uuid4())
    content = b"\x00exact original\xff\n"
    stored = storage.put(key, io.BytesIO(content), max_bytes=100)
    assert stored.key == key
    assert stored.file_size == len(content)
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    with storage.open(key) as source:
        assert source.read() == content
    with pytest.raises(FileExistsError):
        storage.put(key, io.BytesIO(b"replacement"), max_bytes=100)
    with storage.open(key) as source:
        assert source.read() == content
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.open(key)


def test_shared_size_failure_does_not_publish_a_partial_original(storage):
    key = document_storage_key(uuid4(), uuid4())
    with pytest.raises(ValueError, match="size limit"):
        storage.put(key, io.BytesIO(b"123456"), max_bytes=5)
    with pytest.raises(FileNotFoundError):
        storage.open(key)


def test_shared_simultaneous_publication_preserves_one_whole_original(storage):
    key = document_storage_key(uuid4(), uuid4())
    barrier = threading.Barrier(2)

    def publish(content):
        barrier.wait(timeout=5)
        try:
            return storage.put(key, io.BytesIO(content), max_bytes=100).sha256
        except FileExistsError:
            return "existing"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, [b"original-a", b"original-b"]))
    assert results.count("existing") == 1
    with storage.open(key) as source:
        actual = source.read()
    assert actual in {b"original-a", b"original-b"}
    assert hashlib.sha256(actual).hexdigest() in results


@pytest.mark.parametrize(
    "key",
    [
        "../secret",
        "/absolute",
        "org/doc/source",
        "a//b",
        "",
        ".",
        str(uuid4()) + "/" + str(uuid4()) + "/public",
    ],
)
def test_s3_rejects_noncanonical_tenant_original_keys(key):
    adapter = S3ObjectStorage(settings(), client=PrivateS3Fixture())
    for action in (
        lambda: adapter.put(key, io.BytesIO(b"x"), max_bytes=100),
        lambda: adapter.open(key),
        lambda: adapter.delete(key),
    ):
        with pytest.raises(ValueError):
            action()


@pytest.mark.parametrize(
    "change,code",
    [
        ({"versioning": "Suspended"}, "source_version_preservation_required"),
        ({"encrypted": False}, "source_encryption_required"),
        ({"public": True}, "source_public_access_block_required"),
    ],
)
def test_private_versioned_encrypted_readiness_fails_closed(change, code):
    client = PrivateS3Fixture()
    adapter = S3ObjectStorage(settings(), client=client)
    adapter.healthcheck()
    for k, v in change.items():
        setattr(client, k, v)
    with pytest.raises(StorageFailure, match=code):
        adapter.healthcheck()


def test_compatible_no_policy_profile_never_trusts_a_provider_is_public_flag():
    client = PrivateS3Fixture()
    adapter = S3ObjectStorage(settings(s3_private_profile="no-policy"), client=client)
    adapter.healthcheck()
    client.policy = '{"Statement": "even a supposedly private policy requires another profile"}'
    with pytest.raises(StorageFailure, match="source_private_no_policy_required"):
        adapter.healthcheck()
    client.policy = None
    client.grantee = "another-principal"
    with pytest.raises(StorageFailure, match="source_private_acl_required"):
        adapter.healthcheck()


def test_actual_source_verification_preserves_existing_proof_outcomes():
    client = PrivateS3Fixture()
    adapter = S3ObjectStorage(settings(), client=client)
    key = document_storage_key(uuid4(), uuid4())
    stored = adapter.put(key, io.BytesIO(b"exact"), max_bytes=100)
    document = SimpleNamespace(storage_key=key, file_size=5, sha256=stored.sha256)

    def verify():
        return verify_source(adapter, document, Budget(OperationalLimits()), capture=True)

    assert verify() == ("AVAILABLE_VERIFIED", b"exact")
    client.values[key] = b"other"
    assert verify() == ("MISMATCH", None)
    client.outage = True
    assert verify() == ("UNAVAILABLE", None)
    client.outage = False
    client.values.clear()
    assert verify() == ("UNAVAILABLE", None)


def test_remote_actual_bytes_and_wall_work_are_bounded_and_closed():
    source = io.BytesIO(b"123456")
    with BoundedRemoteReader(source, max_bytes=5, deadline=time.monotonic() + 1) as reader:
        with pytest.raises(StorageFailure, match="source_read_size_limit"):
            reader.read()
    assert source.closed
    source = io.BytesIO(b"content")
    with BoundedRemoteReader(source, max_bytes=10, deadline=time.monotonic() - 1) as reader:
        with pytest.raises(StorageFailure, match="source_read_work_budget"):
            reader.read(1)
    assert source.closed


def test_remote_errors_and_cleanup_failure_do_not_disclose_provider_or_content():
    client = PrivateS3Fixture()
    adapter = S3ObjectStorage(settings(), client=client)

    def fail(**kwargs):
        raise failure("AccessDenied", 403)

    client.delete_object = fail
    with pytest.raises(StorageFailure) as error:
        adapter.delete(document_storage_key(uuid4(), uuid4()))
    assert str(error.value) == "source_store_unavailable"
    assert "customer-secret" not in str(error.value)


def test_factory_never_falls_back_to_local_for_incomplete_s3_configuration(tmp_path):
    with pytest.raises(StorageFailure, match="source_store_not_configured"):
        build_storage(
            Settings(_env_file=None, storage_backend="s3", storage_root=tmp_path / "local")
        )
    assert not (tmp_path / "local").exists()


def test_real_sdk_conditional_encrypted_put_shape_and_single_attempt_configuration():
    import boto3
    from botocore.config import Config
    from botocore.stub import ANY, Stubber

    client = boto3.client(
        "s3",
        endpoint_url="http://127.0.0.1:9000",
        region_name="synthetic-region",
        aws_access_key_id="synthetic-only",
        aws_secret_access_key="synthetic-only",
        config=Config(retries={"total_max_attempts": 1}),
    )
    key = document_storage_key(uuid4(), uuid4())
    adapter = S3ObjectStorage(settings(), client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "put_object",
            {"VersionId": "original-v1", "ServerSideEncryption": "AES256"},
            {
                "Bucket": adapter.bucket,
                "Key": key,
                "Body": ANY,
                "ContentLength": 5,
                "ContentType": "application/octet-stream",
                "IfNoneMatch": "*",
                "ServerSideEncryption": "AES256",
                "ChecksumSHA256": base64.b64encode(hashlib.sha256(b"exact").digest()).decode(),
            },
        )
        stored = adapter.put(key, io.BytesIO(b"exact"), max_bytes=100)
        stub.assert_no_pending_responses()
    assert stored.sha256 == hashlib.sha256(b"exact").hexdigest()
    assert client.meta.config.retries["total_max_attempts"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"s3_endpoint_url": "http://public.example.test"},
        {"environment": "production", "s3_endpoint_url": "http://127.0.0.1:9000"},
        {"s3_endpoint_url": "https://objects.example.test/?signed=secret"},
    ],
)
def test_adapter_itself_rejects_unsafe_transports_even_without_app_startup(changes):
    values = dict(
        environment="test",
        s3_bucket="synthetic-originals",
        s3_region="synthetic-region",
        s3_endpoint_url="https://objects.example.test",
    )
    values.update(changes)
    with pytest.raises(StorageFailure, match="source_secure_endpoint_required"):
        S3ObjectStorage(Settings(_env_file=None, **values), client=PrivateS3Fixture())
