"""Private bounded S3-compatible originals; no financial or public URL authority."""

import base64
import hashlib
import io
import tempfile
import time
from typing import BinaryIO
from urllib.parse import urlsplit
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.modules.storage import StoredObject


class StorageFailure(OSError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def original_key(key: str) -> str:
    pieces = key.split("/")
    if len(pieces) != 3 or pieces[2] != "source":
        raise ValueError("Invalid original object key")
    try:
        if str(UUID(pieces[0])) != pieces[0] or str(UUID(pieces[1])) != pieces[1]:
            raise ValueError
    except ValueError:
        raise ValueError("Invalid original object namespace") from None
    return key


class BoundedRemoteReader(io.RawIOBase):
    def __init__(self, body, *, max_bytes: int, deadline: float):
        self.body, self.max_bytes, self.deadline = body, max_bytes, deadline
        self.total = 0

    def readable(self):
        return True

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("Source stream is closed")
        if size == 0:
            return b""
        target = self.max_bytes + 1 if size < 0 else min(size, self.max_bytes + 1)
        output = bytearray()
        while len(output) < target:
            if time.monotonic() >= self.deadline:
                raise StorageFailure("source_read_work_budget")
            try:
                chunk = self.body.read(min(64 * 1024, target - len(output)))
            except (BotoCoreError, OSError):
                raise StorageFailure("source_read_unavailable") from None
            if time.monotonic() >= self.deadline:
                raise StorageFailure("source_read_work_budget")
            if not chunk:
                break
            self.total += len(chunk)
            if self.total > self.max_bytes:
                raise StorageFailure("source_read_size_limit")
            output.extend(chunk)
        return bytes(output)

    def close(self):
        if not self.closed:
            try:
                self.body.close()
            finally:
                super().close()


class DeadlineFile:
    def __init__(self, source, deadline):
        self.source, self.deadline = source, deadline

    def read(self, size=-1):
        if time.monotonic() >= self.deadline:
            raise StorageFailure("source_write_work_budget")
        value = self.source.read(size)
        if time.monotonic() >= self.deadline:
            raise StorageFailure("source_write_work_budget")
        return value

    def seek(self, *args):
        return self.source.seek(*args)

    def tell(self):
        return self.source.tell()


class S3ObjectStorage:
    """No overwrite, no presigned URLs, no filename/object content in errors.

    Provider qualification must demonstrate these APIs really enforce their contracts.
    A compatible CI service is engineering evidence, never cloud/privacy qualification.
    """

    def __init__(self, settings, *, client=None):
        if not settings.s3_bucket or not settings.s3_endpoint_url or not settings.s3_region:
            raise StorageFailure("source_store_not_configured")
        endpoint = urlsplit(settings.s3_endpoint_url)
        local_http = (
            settings.environment != "production"
            and endpoint.scheme == "http"
            and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if (
            not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or (endpoint.fragment or (endpoint.scheme != "https" and not local_http))
        ):
            raise StorageFailure("source_secure_endpoint_required")
        self.bucket = settings.s3_bucket
        self.max_bytes = 100 * 1024 * 1024  # Existing maximum admitted original size.
        self.work_seconds = settings.s3_work_seconds
        self.private_profile = settings.s3_private_profile
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=(
                settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None
            ),
            aws_secret_access_key=(
                settings.s3_secret_access_key.get_secret_value()
                if settings.s3_secret_access_key
                else None
            ),
            config=Config(
                connect_timeout=settings.s3_timeout_seconds,
                read_timeout=settings.s3_timeout_seconds,
                retries={"mode": "standard", "total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    def _call(self, method, **values):
        try:
            return getattr(self.client, method)(Bucket=self.bucket, **values)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if method == "get_object" and code in {"NoSuchKey", "404"}:
                raise FileNotFoundError("source_unavailable") from None
            if method == "put_object" and (code == "PreconditionFailed" or status == 412):
                raise FileExistsError("object_already_exists") from None
            if method == "put_object" and (code == "ConditionalRequestConflict" or status == 409):
                raise StorageFailure("source_publish_retry") from None
            raise StorageFailure("source_store_unavailable") from None
        except (BotoCoreError, OSError):
            # A timeout after conditional PUT is ambiguous. Never overwrite or delete it
            # blindly; reconciled inventory handles orphaned publications explicitly.
            raise StorageFailure("source_store_unavailable") from None

    def put(self, key: str, source: BinaryIO, *, max_bytes: int) -> StoredObject:
        key = original_key(key)
        if not 1 <= max_bytes <= self.max_bytes:
            raise ValueError("Invalid original size bound")
        deadline, checksum, size = time.monotonic() + self.work_seconds, hashlib.sha256(), 0
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as captured:
            while chunk := source.read(64 * 1024):
                if time.monotonic() >= deadline:
                    raise StorageFailure("source_write_work_budget")
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("Document exceeds size limit")
                checksum.update(chunk)
                captured.write(chunk)
            captured.seek(0)
            result = self._call(
                "put_object",
                Key=key,
                Body=DeadlineFile(captured, deadline),
                ContentLength=size,
                ContentType="application/octet-stream",
                IfNoneMatch="*",
                ServerSideEncryption="AES256",
                ChecksumSHA256=base64.b64encode(checksum.digest()).decode("ascii"),
            )
            if time.monotonic() >= deadline:
                raise StorageFailure("source_write_work_budget")
            if result.get("ServerSideEncryption") != "AES256" or not result.get("VersionId"):
                raise StorageFailure("source_publication_contract_unverified")
        return StoredObject(key=key, file_size=size, sha256=checksum.hexdigest())

    def open(self, key: str) -> BinaryIO:
        deadline = time.monotonic() + self.work_seconds
        result = self._call("get_object", Key=original_key(key))
        body = result.get("Body")
        if body is None:
            raise StorageFailure("source_read_unavailable")
        if (
            time.monotonic() >= deadline
            or not isinstance(result.get("ContentLength"), int)
            or not 0 <= result["ContentLength"] <= self.max_bytes
            or result.get("ServerSideEncryption") != "AES256"
        ):
            body.close()
            raise StorageFailure("source_read_contract_unverified")
        return BoundedRemoteReader(body, max_bytes=self.max_bytes, deadline=deadline)

    def delete(self, key: str) -> None:
        # Used only for failed-new-upload compensation via the preservation wrapper.
        # Never delete versions. Production IAM should deny ordinary source deletion;
        # protected reconciliation operators handle any denied orphan cleanup.
        self._call("delete_object", Key=original_key(key))

    def healthcheck(self) -> None:
        start = time.monotonic()
        if self._call("get_bucket_versioning").get("Status") != "Enabled":
            raise StorageFailure("source_version_preservation_required")
        encryption = self._call("get_bucket_encryption")
        rules = encryption.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
        if not any(
            r.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256"
            for r in rules
        ):
            raise StorageFailure("source_encryption_required")
        if self.private_profile == "public-block":
            block = self._call("get_public_access_block").get("PublicAccessBlockConfiguration", {})
            if not all(
                block.get(name) is True
                for name in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            ):
                raise StorageFailure("source_public_access_block_required")
        else:
            # Some S3-compatible private services do not implement public-block APIs.
            # Only a bucket with NO policy and owner-only ACL is admitted in this profile.
            # Do not rely on provider IsPublic flags which may have different semantics.
            acl = self._call("get_bucket_acl")
            owner = acl.get("Owner", {}).get("ID")
            if not owner or any(
                g.get("Grantee", {}).get("Type") != "CanonicalUser"
                or g["Grantee"].get("ID") != owner
                for g in acl.get("Grants", [])
            ):
                raise StorageFailure("source_private_acl_required")
            try:
                self.client.get_bucket_policy(Bucket=self.bucket)
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "NoSuchBucketPolicy":
                    raise StorageFailure("source_private_policy_unverified") from None
            except (BotoCoreError, OSError):
                raise StorageFailure("source_private_policy_unverified") from None
            else:
                raise StorageFailure("source_private_no_policy_required")
        if time.monotonic() - start >= self.work_seconds:
            raise StorageFailure("source_health_work_budget")
