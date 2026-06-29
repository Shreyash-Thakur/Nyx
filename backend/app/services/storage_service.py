import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from app.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def _build_local_path(self, filename: str, invoice_id: uuid.UUID) -> Path:
        today = datetime.now(timezone.utc)
        relative = Path("invoices") / str(today.year) / f"{today.month:02d}" / str(invoice_id)
        full_dir = Path(settings.UPLOAD_DIR) / relative
        full_dir.mkdir(parents=True, exist_ok=True)
        return full_dir / filename

    async def save(
        self,
        content: bytes,
        filename: str,
        invoice_id: uuid.UUID,
        content_type: str = "application/pdf",
    ) -> tuple[str, str]:
        """Returns (storage_path, sha256_checksum)."""
        checksum = hashlib.sha256(content).hexdigest()

        if settings.STORAGE_BACKEND == "s3":
            storage_path = await self._save_s3(content, filename, invoice_id, content_type)
        else:
            storage_path = await self._save_local(content, filename, invoice_id)

        logger.info("file_saved", path=storage_path, size=len(content))
        return storage_path, checksum

    async def _save_local(self, content: bytes, filename: str, invoice_id: uuid.UUID) -> str:
        dest = self._build_local_path(filename, invoice_id)
        try:
            async with aiofiles.open(dest, "wb") as f:
                await f.write(content)
        except OSError as exc:
            raise StorageError(f"Failed to write file: {exc}") from exc
        # Return path relative to UPLOAD_DIR
        return str(dest.relative_to(settings.UPLOAD_DIR))

    async def _save_s3(
        self,
        content: bytes,
        filename: str,
        invoice_id: uuid.UUID,
        content_type: str,
    ) -> str:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        today = datetime.now(timezone.utc)
        key = f"invoices/{today.year}/{today.month:02d}/{invoice_id}/{filename}"

        kwargs: dict = {
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
            "region_name": settings.S3_REGION,
        }
        s3 = boto3.client("s3", **{k: v for k, v in kwargs.items() if v})
        try:
            s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"S3 upload failed: {exc}") from exc
        return f"s3://{settings.S3_BUCKET_NAME}/{key}"

    async def read(self, storage_path: str) -> bytes:
        if storage_path.startswith("s3://"):
            return self._read_s3_sync(storage_path)
        full_path = Path(settings.UPLOAD_DIR) / storage_path
        if not full_path.exists():
            raise StorageError(f"File not found: {storage_path}")
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    def read_sync(self, storage_path: str) -> bytes:
        """Synchronous read for worker / queue contexts.

        Workers are synchronous (and the inline-queue path executes inside the
        request's running event loop), so they must not drive an event loop to
        read a file. boto3 is synchronous anyway and local reads are plain I/O.
        """
        if storage_path.startswith("s3://"):
            return self._read_s3_sync(storage_path)
        full_path = Path(settings.UPLOAD_DIR) / storage_path
        if not full_path.exists():
            raise StorageError(f"File not found: {storage_path}")
        return full_path.read_bytes()

    def _read_s3_sync(self, s3_uri: str) -> bytes:
        import boto3

        parts = s3_uri[5:].split("/", 1)
        bucket, key = parts[0], parts[1]
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
