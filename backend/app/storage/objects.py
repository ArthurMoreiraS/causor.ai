"""Storage privado de objetos (documentos dos autos).

Bucket privado, sem URL pública: o agente local sobe arquivos por URL
pré-assinada de 15 minutos e o backend recomputa o SHA-256 ao ingerir —
o hash declarado pelo agente não é prova suficiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256 as sha256_digest
from pathlib import Path, PurePosixPath
import os
import time
from typing import Protocol
from uuid import UUID, uuid4

from botocore.exceptions import ClientError

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


@dataclass(frozen=True)
class DownloadTicket:
    key: str
    url: str
    expires_in: int


class ObjectStore(Protocol):
    @property
    def store_id(self) -> str: ...

    def exists(self, key: str) -> bool: ...

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    def get_bytes(self, key: str) -> bytes: ...

    def download_to(self, key: str, destination: Path) -> None: ...

    def delete(self, key: str) -> None: ...

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket: ...

    def create_download_ticket(self, key: str, *, expires_in: int = 300) -> DownloadTicket: ...


def _safe_key(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or "\\" in key or not key.strip():
        raise UnsafeObjectKeyError("unsafe object key")
    return str(path)


class LocalObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root / ".causor-store-id"
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(str(uuid4()))
                handle.flush()
                os.fsync(handle.fileno())
        for _ in range(100):
            identity = marker.read_text(encoding="ascii").strip()
            if identity:
                break
            time.sleep(0.01)
        else:
            raise RuntimeError("object store identity marker is empty")
        try:
            identity = str(UUID(identity))
        except ValueError as exc:
            raise RuntimeError("object store identity marker is invalid") from exc
        self.store_id = f"local:{identity}"

    def exists(self, key: str) -> bool:
        safe = _safe_key(key)
        return (self.root / safe).is_file()

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

    def delete(self, key: str) -> None:
        safe = _safe_key(key)
        (self.root / safe).unlink(missing_ok=True)

    def create_download_ticket(self, key: str, *, expires_in: int = 300) -> DownloadTicket:
        # Nunca expõe caminho de filesystem: a rota da API troca este marcador
        # por uma URL autenticada de conteúdo.
        safe = _safe_key(key)
        return DownloadTicket(key=safe, url=f"local-object://{safe}", expires_in=expires_in)

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
        identity = "\0".join((settings.object_store_endpoint or "aws", self.bucket, settings.object_store_region))
        self.store_id = f"s3:{sha256_digest(identity.encode()).hexdigest()}"

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_safe_key(key))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

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
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(safe) from exc
            raise
        return response["Body"].read()

    def download_to(self, key: str, destination: Path) -> None:
        safe = _safe_key(key)
        self.client.download_file(self.bucket, safe, str(destination))

    def delete(self, key: str) -> None:
        safe = _safe_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=safe)

    def create_download_ticket(self, key: str, *, expires_in: int = 300) -> DownloadTicket:
        safe = _safe_key(key)
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": safe},
            ExpiresIn=expires_in,
            HttpMethod="GET",
        )
        return DownloadTicket(key=safe, url=url, expires_in=expires_in)

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
