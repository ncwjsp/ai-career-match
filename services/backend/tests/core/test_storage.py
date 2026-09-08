"""Storage adapter behavior. No AWS account or network access is used."""

import pytest

from app.contracts.models import FileRef
from app.core.errors import DependencyUnavailable, InvalidRequest, NotFound
from app.core.settings import Settings
from app.core.storage import LocalObjectStore, S3ObjectStore, build_object_store

PDF = b"%PDF-1.7 synthetic"


class FakeS3:
    """The three calls the adapter makes, plus a way to force failures."""

    def __init__(self, fail_with: Exception | None = None):
        self.objects: dict[str, dict] = {}
        self.fail_with = fail_with

    def put_object(self, Bucket, Key, Body, ContentType, ServerSideEncryption):  # noqa: N803
        if self.fail_with:
            raise self.fail_with
        self.objects[Key] = {
            "bucket": Bucket,
            "body": Body,
            "type": ContentType,
            "sse": ServerSideEncryption,
        }

    def get_object(self, Bucket, Key):  # noqa: N803
        if self.fail_with:
            raise self.fail_with
        if Key not in self.objects:
            raise missing_key_error()
        return {"Body": _Body(self.objects[Key]["body"])}

    def delete_object(self, Bucket, Key):  # noqa: N803
        if self.fail_with:
            raise self.fail_with
        self.objects.pop(Key, None)


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


def missing_key_error() -> Exception:
    error = Exception("missing")
    error.response = {"Error": {"Code": "NoSuchKey"}}
    return error


def outage() -> Exception:
    error = Exception("throttled")
    error.response = {"Error": {"Code": "SlowDown"}}
    return error


@pytest.fixture
def local(tmp_path):
    return LocalObjectStore(tmp_path, "resumes/")


def test_local_round_trip_and_delete(local):
    ref = local.put(PDF, "application/pdf")
    assert local.read(ref) == PDF
    local.delete(ref)
    with pytest.raises(NotFound):
        local.read(ref)


def test_local_delete_is_idempotent(local):
    ref = local.put(PDF, "application/pdf")
    local.delete(ref)
    local.delete(ref)


def test_keys_are_opaque_unique_and_prefixed(local):
    first = local.put(PDF, "application/pdf")
    second = local.put(PDF, "application/pdf")
    assert first.object_key != second.object_key
    assert first.object_key.startswith("resumes/resume-")


def test_a_key_cannot_escape_the_store(local):
    with pytest.raises(InvalidRequest):
        local.read(FileRef(object_key="../../etc/passwd", media_type="application/pdf"))


def test_s3_round_trip_uses_the_configured_bucket_and_encryption():
    client = FakeS3()
    store = S3ObjectStore("career-resumes", "resumes/", client=client)
    ref = store.put(PDF, "application/pdf")
    stored = client.objects[ref.object_key]
    assert (stored["bucket"], stored["sse"]) == ("career-resumes", "AES256")
    assert store.read(ref) == PDF
    store.delete(ref)
    assert client.objects == {}


def test_s3_missing_object_is_not_found_not_an_outage():
    store = S3ObjectStore("career-resumes", client=FakeS3())
    with pytest.raises(NotFound):
        store.read(FileRef(object_key="resume-absent", media_type="application/pdf"))


def test_s3_deleting_an_absent_object_succeeds():
    client = FakeS3()
    store = S3ObjectStore("career-resumes", client=client)
    store.delete(FileRef(object_key="resume-absent", media_type="application/pdf"))


def test_s3_failures_surface_as_a_retryable_dependency_error():
    store = S3ObjectStore("career-resumes", client=FakeS3(fail_with=outage()))
    with pytest.raises(DependencyUnavailable) as put_error:
        store.put(PDF, "application/pdf")
    assert put_error.value.retryable
    with pytest.raises(DependencyUnavailable):
        store.read(FileRef(object_key="resume-x", media_type="application/pdf"))
    with pytest.raises(DependencyUnavailable):
        store.delete(FileRef(object_key="resume-x", media_type="application/pdf"))


def test_s3_requires_a_bucket_name():
    with pytest.raises(ValueError, match="bucket"):
        S3ObjectStore("")


def test_the_default_configuration_builds_the_local_store(tmp_path):
    store = build_object_store(Settings(object_store_local_dir=str(tmp_path)))
    assert isinstance(store, LocalObjectStore)
    assert store.read(store.put(PDF, "application/pdf")) == PDF
