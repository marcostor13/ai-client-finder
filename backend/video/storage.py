"""
S3 storage helpers for video files.
All keys follow: videos/{user_email}/{job_id}/{filename}
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from backend.database import settings


def _client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _key(user_email: str, job_id: str, filename: str) -> str:
    safe_email = user_email.replace("@", "_at_").replace(".", "_")
    return f"videos/{safe_email}/{job_id}/{filename}"


# ── Sync helpers (run in thread executor) ─────────────────────────────────────

def _upload_sync(local_path: str, s3_key: str, content_type: str = "video/mp4") -> str:
    s3 = _client()
    s3.upload_file(
        local_path,
        settings.s3_bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return s3_key


def _download_sync(s3_key: str, local_path: str) -> str:
    s3 = _client()
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3.download_file(settings.s3_bucket, s3_key, local_path)
    return local_path


def _presigned_sync(s3_key: str, expires: int = 3600) -> str:
    s3 = _client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key},
        ExpiresIn=expires,
    )
    return url


def _delete_sync(s3_key: str) -> None:
    s3 = _client()
    s3.delete_object(Bucket=settings.s3_bucket, Key=s3_key)


def _list_sync(prefix: str) -> list[str]:
    s3 = _client()
    resp = s3.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]


# ── Async wrappers ─────────────────────────────────────────────────────────────

async def upload_file(local_path: str, user_email: str, job_id: str,
                      filename: str, content_type: str = "video/mp4") -> str:
    key = _key(user_email, job_id, filename)
    await asyncio.to_thread(_upload_sync, local_path, key, content_type)
    return key


async def download_file(s3_key: str, local_path: str) -> str:
    return await asyncio.to_thread(_download_sync, s3_key, local_path)


async def get_presigned_url(s3_key: str, expires: int = 7200) -> str:
    return await asyncio.to_thread(_presigned_sync, s3_key, expires)


async def delete_file(s3_key: str) -> None:
    await asyncio.to_thread(_delete_sync, s3_key)


async def delete_job_files(user_email: str, job_id: str) -> None:
    safe_email = user_email.replace("@", "_at_").replace(".", "_")
    prefix = f"videos/{safe_email}/{job_id}/"
    keys = await asyncio.to_thread(_list_sync, prefix)
    for key in keys:
        await asyncio.to_thread(_delete_sync, key)
