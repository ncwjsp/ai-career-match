"""`ObjectStore` adapters for original resumes. Owner: M3 (C-01).

Two adapters implement `app.contracts.interfaces.ObjectStore`:

  - `LocalObjectStore` writes under one directory. It is for tests, CI and
    offline development only: the API and the worker are separate processes and
    in deployment they do not share a filesystem.
  - `S3ObjectStore` is the deployment adapter required by the 2026-09-08
    revision. It never returns a public or presigned URL, so every read stays
    authorized by the application.

Keys are opaque (`app.core.ids`) and carry no candidate data, so a leaked key
reveals nothing and cannot be guessed from a candidate identifier. A missing
object raises `NotFound`; a failing bucket raises `DependencyUnavailable` so the
caller reports an outage instead of an empty resume.
"""

from __future__ import annotations

from pathlib import Path

from app.contracts.models import FileRef
from app.core.errors import DependencyUnavailable, InvalidRequest, NotFound
from app.core.ids import new_id
from app.core.settings import Settings

_KEY_PREFIX = "resume"


def _new_key(prefix: str) -> str:
    return f"{prefix}{new_id(_KEY_PREFIX)}"


def _reject_traversal(object_key: str) -> None:
    # Keys are generated, never supplied by a user; this guards a future caller.
    if not object_key or object_key.startswith("/") or ".." in object_key.split("/"):
        raise InvalidRequest("An object key must be a generated relative key.")


class LocalObjectStore:
    """Filesystem-backed store for tests and single-process development."""

    def __init__(self, directory: str | Path, prefix: str = ""):
        self._root = Path(directory)
        self._prefix = prefix

    def _path(self, object_key: str) -> Path:
        _reject_traversal(object_key)
        return self._root / object_key

    def put(self, content: bytes, media_type: str) -> FileRef:
        key = _new_key(self._prefix)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        # The media type lives on the FileRef the caller persists, not beside the bytes.
        return FileRef(object_key=key, media_type=media_type)

    def read(self, file: FileRef) -> bytes:
        path = self._path(file.object_key)
        if not path.is_file():
            raise NotFound("The stored file no longer exists.")
        return path.read_bytes()

    def delete(self, file: FileRef) -> None:
        self._path(file.object_key).unlink(missing_ok=True)


class S3ObjectStore:
    """Private-bucket adapter. `client` is injected so tests need no network."""

    def __init__(self, bucket: str, prefix: str = "", client=None, region: str | None = None):
        if not bucket:
            raise ValueError("S3ObjectStore requires a bucket name.")
        self._bucket = bucket
        self._prefix = prefix
        self._client = client
        self._region = region

    @property
    def client(self):
        if self._client is None:
            self._client = _build_s3_client(self._region, None)
        return self._client

    def put(self, content: bytes, media_type: str) -> FileRef:
        key = _new_key(self._prefix)
        try:
            self.client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=media_type,
                # Bucket policy also enforces this; the request states it too.
                ServerSideEncryption="AES256",
            )
        except Exception as error:  # noqa: BLE001 - any client failure is an outage
            raise DependencyUnavailable("The resume bucket rejected the upload.") from error
        return FileRef(object_key=key, media_type=media_type)

    def read(self, file: FileRef) -> bytes:
        _reject_traversal(file.object_key)
        try:
            response = self.client.get_object(Bucket=self._bucket, Key=file.object_key)
        except Exception as error:  # noqa: BLE001
            if _is_missing_key(error):
                raise NotFound("The stored file no longer exists.") from error
            raise DependencyUnavailable("The resume bucket is unavailable.") from error
        return response["Body"].read()

    def delete(self, file: FileRef) -> None:
        _reject_traversal(file.object_key)
        try:
            self.client.delete_object(Bucket=self._bucket, Key=file.object_key)
        except Exception as error:  # noqa: BLE001
            if _is_missing_key(error):
                return  # Deleting an absent object is the requested end state.
            raise DependencyUnavailable("The resume bucket is unavailable.") from error


def _is_missing_key(error: Exception) -> bool:
    code = getattr(error, "response", {}).get("Error", {}).get("Code")
    return code in {"NoSuchKey", "404", "NotFound"}


def _build_s3_client(region: str | None, endpoint_url: str | None):
    try:
        import boto3
    except ModuleNotFoundError as error:  # pragma: no cover - boto3 is a pinned dependency
        raise DependencyUnavailable("boto3 is required for S3 storage.") from error
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url or None)


def build_object_store(settings: Settings):
    """Build the store the configuration asks for. Called once at startup."""
    if settings.object_store_backend == "local":
        return LocalObjectStore(settings.object_store_local_dir, settings.resume_object_prefix)
    return S3ObjectStore(
        bucket=settings.resume_bucket,
        prefix=settings.resume_object_prefix,
        client=_build_s3_client(settings.aws_region, settings.aws_s3_endpoint_url),
        region=settings.aws_region,
    )
