from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor

from botocore.exceptions import ClientError

import pytest

from app.storage.objects import LocalObjectStore, S3ObjectStore, UnsafeObjectKeyError


def test_local_store_round_trip_and_hash(tmp_path):
    store = LocalObjectStore(tmp_path)
    data = b"%PDF-1.4\n%%EOF\n"
    stored = store.put_bytes("tenant/1/process/2/doc.pdf", data, "application/pdf")
    assert stored.sha256 == sha256(data).hexdigest()
    assert store.get_bytes(stored.key) == data


def test_local_identity_survives_restart_and_concurrent_initialization(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        identities = list(pool.map(lambda _: LocalObjectStore(tmp_path).store_id, range(8)))
    assert len(set(identities)) == 1
    assert LocalObjectStore(tmp_path).store_id == identities[0]
    assert LocalObjectStore(tmp_path / "other").store_id != identities[0]


def test_corrupt_local_identity_fails_closed(tmp_path):
    (tmp_path / ".causor-store-id").write_text("invalid", encoding="ascii")
    with pytest.raises(RuntimeError, match="identity marker is invalid"):
        LocalObjectStore(tmp_path)


def test_s3_missing_get_is_normalized_to_file_not_found():
    store = S3ObjectStore.__new__(S3ObjectStore)
    store.bucket = "test"

    class MissingClient:
        def get_object(self, **_kwargs):
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")

    store.client = MissingClient()
    with pytest.raises(FileNotFoundError):
        store.get_bytes("missing.pdf")


def test_s3_head_forbidden_is_not_misreported_as_missing():
    store = S3ObjectStore.__new__(S3ObjectStore)
    store.bucket = "test"

    class ForbiddenClient:
        def head_object(self, **_kwargs):
            raise ClientError({"Error": {"Code": "403", "Message": "forbidden"}}, "HeadObject")

    store.client = ForbiddenClient()
    with pytest.raises(ClientError):
        store.exists("private.pdf")


@pytest.mark.parametrize("key", ["../secret", "/absolute", "tenant\\escape"])
def test_local_store_rejects_unsafe_key(tmp_path, key):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(UnsafeObjectKeyError):
        store.put_bytes(key, b"x", "application/octet-stream")
