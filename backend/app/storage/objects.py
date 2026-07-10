"""Storage privado de objetos (documentos dos autos).

Bucket privado, sem URL pública: o agente local sobe arquivos por URL
pré-assinada de 15 minutos e o backend recomputa o SHA-256 ao ingerir —
o hash declarado pelo agente não é prova suficiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256 as sha256_digest
from pathlib import Path, PurePosixPath
from typing import Protocol

import boto3

from app.settings import settings


class UnsafeObjectKeyError(ValueError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    uri: str
    size_bytes: int
    sha256: str
    content_type: str


@dataclass(frozen=True)
class UploadTicket:
    key: str
    method: str
    url: str
    headers: dict[str, str]
    expires_in: int


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    def get_bytes(self, key: str) -> bytes: ...

    def download_to(self, key: str, destination: Path) -> None: ...

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket: ...


def _safe_key(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or "\\" in key or not key.strip():
        raise UnsafeObjectKeyError("unsafe object key")
    return str(path)


class LocalObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe = _safe_key(key)
        target = (self.root / safe).resolve()
        if self.root not in target.parents:
            raise UnsafeObjectKeyError("object escaped storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = sha256_digest(data).hexdigest()
        return StoredObject(safe, f"local-object://{safe}", len(data), digest, content_type)

    def get_bytes(self, key: str) -> bytes:
        safe = _safe_key(key)
        return (self.root / safe).read_bytes()

    def download_to(self, key: str, destination: Path) -> None:
        safe = _safe_key(key)
        destination.write_bytes((self.root / safe).read_bytes())

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket:
        safe = _safe_key(key)
        return UploadTicket(
            key=safe,
            method="PUT",
            url=f"local-object://{safe}",
            headers={
                "content-type": content_type,
                "x-causor-sha256": sha256,
                "x-causor-size": str(size_bytes),
            },
            expires_in=900,
        )


class S3ObjectStore:
    def __init__(self):
        self.bucket = settings.object_store_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_store_endpoint or None,
            region_name=settings.object_store_region,
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe = _safe_key(key)
        digest = sha256_digest(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=safe,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return StoredObject(safe, f"s3://{self.bucket}/{safe}", len(data), digest, content_type)

    def get_bytes(self, key: str) -> bytes:
        safe = _safe_key(key)
        response = self.client.get_object(Bucket=self.bucket, Key=safe)
        return response["Body"].read()

    def download_to(self, key: str, destination: Path) -> None:
        safe = _safe_key(key)
        self.client.download_file(self.bucket, safe, str(destination))

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket:
        safe = _safe_key(key)
        params = {
            "Bucket": self.bucket,
            "Key": safe,
            "ContentType": content_type,
            "Metadata": {"sha256": sha256, "size": str(size_bytes)},
        }
        url = self.client.generate_presigned_url(
            "put_object", Params=params, ExpiresIn=900, HttpMethod="PUT"
        )
        return UploadTicket(
            key=safe,
            method="PUT",
            url=url,
            headers={
                "content-type": content_type,
                "x-amz-meta-sha256": sha256,
                "x-amz-meta-size": str(size_bytes),
            },
            expires_in=900,
        )


def get_object_store() -> ObjectStore:
    if settings.object_store_provider == "localdev":
        return LocalObjectStore(settings.object_store_local_path)
    if settings.object_store_provider == "s3":
        return S3ObjectStore()
    raise ValueError(f"unknown object store provider: {settings.object_store_provider}")
