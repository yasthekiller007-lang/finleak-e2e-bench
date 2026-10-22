"""Synthetic isolated S3 service acceptance, excluded from production images."""

import base64
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.s3_storage import S3ObjectStorage, StorageFailure
from app.modules.storage import document_storage_key
from tests.test_s3_storage import (
    test_shared_simultaneous_publication_preserves_one_whole_original,
    test_shared_size_failure_does_not_publish_a_partial_original,
    test_shared_storage_exact_bytes_size_checksum_and_no_overwrite,
)

SOURCE_SHA = "9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a"


def main():
    executable = os.environ.get("PHASE7_MINIO_BINARY") or shutil.which("minio")
    if not executable:
        raise RuntimeError("Pinned synthetic S3 service binary is required")
    build_info = subprocess.check_output(["go", "version", "-m", executable]).decode()
    if SOURCE_SHA[:12] not in build_info:
        raise RuntimeError("Synthetic S3 binary does not match pinned source")
    binary_hash = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="phase7-s3-") as scratch:
        root = Path(scratch)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        endpoint = f"http://127.0.0.1:{port}"
        access, secret = "ci-" + uuid4().hex, secrets.token_urlsafe(32)
        environment = {
            "PATH": os.defpath,
            "MINIO_ROOT_USER": access,
            "MINIO_ROOT_PASSWORD": secret,
            "MINIO_BROWSER": "off",
            "MINIO_KMS_SECRET_KEY": "ci-synthetic:" + base64.b64encode(os.urandom(32)).decode(),
        }
        # Service receives no application/runner credentials. Its logs stay private.
        with (root / "private-service.log").open("wb") as output:
            process = subprocess.Popen(
                [executable, "server", str(root / "data"), "--address", f"127.0.0.1:{port}"],
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            try:
                end = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Synthetic S3 service startup failed; private diagnostics"
                        )
                    try:
                        with urlopen(endpoint + "/minio/health/ready", timeout=1) as response:
                            if response.status == 200:
                                break
                    except (URLError, OSError):
                        if time.monotonic() >= end:
                            raise RuntimeError("Synthetic S3 startup budget exceeded") from None
                        time.sleep(0.2)
                settings = Settings(
                    _env_file=None,
                    environment="test",
                    s3_bucket="phase7-synthetic-originals",
                    s3_endpoint_url=endpoint,
                    s3_region="us-east-1",
                    s3_private_profile="no-policy",
                    s3_access_key_id=SecretStr(access),
                    s3_secret_access_key=SecretStr(secret),
                )
                adapter = S3ObjectStorage(settings)
                # An HTTP health response can precede authenticated S3
                # initialization. Qualify startup with a read-only operation;
                # retry only this known startup state within a bounded budget.
                end = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Synthetic S3 service exited during readiness")
                    try:
                        adapter.client.list_buckets()
                        break
                    except ClientError as error:
                        if error.response["Error"]["Code"] != "XMinioServerNotInitialized":
                            raise
                        if time.monotonic() >= end:
                            raise RuntimeError("Synthetic S3 readiness budget exceeded") from None
                        time.sleep(0.2)
                adapter.client.create_bucket(Bucket=settings.s3_bucket)
                adapter.client.put_bucket_versioning(
                    Bucket=settings.s3_bucket, VersioningConfiguration={"Status": "Enabled"}
                )
                adapter.client.put_bucket_encryption(
                    Bucket=settings.s3_bucket,
                    ServerSideEncryptionConfiguration={
                        "Rules": [
                            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                )
                # MinIO deliberately returns a dummy ACL with no owner identity.
                # The production profile must reject this unverified privacy shape;
                # do not relax the gate to make synthetic conformance pass.
                try:
                    adapter.healthcheck()
                except StorageFailure as error:
                    assert error.code == "source_private_acl_required"
                else:
                    raise AssertionError("Dummy owner ACL must not satisfy private readiness")
                assert (
                    adapter.client.get_bucket_versioning(Bucket=settings.s3_bucket)["Status"]
                    == "Enabled"
                )
                assert (
                    adapter.client.get_bucket_encryption(Bucket=settings.s3_bucket)[
                        "ServerSideEncryptionConfiguration"
                    ]["Rules"][0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
                    == "AES256"
                )
                try:
                    adapter.client.get_bucket_policy(Bucket=settings.s3_bucket)
                except ClientError as error:
                    assert error.response["Error"]["Code"] == "NoSuchBucketPolicy"
                else:
                    raise AssertionError("Synthetic bucket must have no public policy")
                test_shared_storage_exact_bytes_size_checksum_and_no_overwrite(adapter)
                test_shared_size_failure_does_not_publish_a_partial_original(adapter)
                test_shared_simultaneous_publication_preserves_one_whole_original(adapter)
                key = document_storage_key(uuid4(), uuid4())
                adapter.put(key, io.BytesIO(b"synthetic private sentinel"), max_bytes=100)
                unsigned = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    region_name="us-east-1",
                    config=Config(signature_version=UNSIGNED, retries={"total_max_attempts": 1}),
                )
                try:
                    unsigned.get_object(Bucket=settings.s3_bucket, Key=key)
                except ClientError as error:
                    assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 403
                else:
                    raise AssertionError("Anonymous original read must fail")
                versions = adapter.client.list_object_versions(
                    Bucket=settings.s3_bucket, Prefix=key
                )
                assert len(versions.get("Versions", [])) == 1
                report = {
                    "kind": "synthetic-isolated-S3-conformance",
                    "release_sha": os.environ.get("RELEASE_SHA", "local-not-release-qualification"),
                    "service_source_sha": SOURCE_SHA,
                    "service_binary_sha256": binary_hash,
                    "cases": [
                        "unverifiable-owner-acl-fails-closed",
                        "exact-no-overwrite-cleanup",
                        "oversize-no-partial",
                        "concurrent-publication",
                        "anonymous-original-denied",
                        "preserved-original-version",
                    ],
                    "result": "PASS",
                    "real_provider_evidence": False,
                    "production_private_readiness": "BLOCKED: synthetic service dummy owner ACL",
                }
                print(json.dumps(report, sort_keys=True))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
