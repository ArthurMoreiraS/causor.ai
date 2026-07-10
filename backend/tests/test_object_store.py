from hashlib import sha256

import pytest

from app.storage.objects import LocalObjectStore, UnsafeObjectKeyError


def test_local_store_round_trip_and_hash(tmp_path):
    store = LocalObjectStore(tmp_path)
    data = b"%PDF-1.4\n%%EOF\n"
    stored = store.put_bytes("tenant/1/process/2/doc.pdf", data, "application/pdf")
    assert stored.sha256 == sha256(data).hexdigest()
    assert store.get_bytes(stored.key) == data


@pytest.mark.parametrize("key", ["../secret", "/absolute", "tenant\\escape"])
def test_local_store_rejects_unsafe_key(tmp_path, key):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(UnsafeObjectKeyError):
        store.put_bytes(key, b"x", "application/octet-stream")
