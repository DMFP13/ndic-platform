"""
Storage Service — Animal Passport Photos
─────────────────────────────────────────
Selects backend via STORAGE_BACKEND environment variable:

  local  (default) — saves bytes to LOCAL_UPLOAD_DIR on disk
                     served by FastAPI StaticFiles at /uploads
  s3               — uploads to S3_BUCKET using boto3
                     upgrade path: set STORAGE_BACKEND=s3 and provide
                     S3_BUCKET, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

To switch to S3 in production:
  1. pip install boto3
  2. Set env vars: STORAGE_BACKEND=s3  S3_BUCKET=<bucket>  S3_REGION=<region>
  3. Optionally set S3_BASE_URL for a CloudFront CDN prefix
  4. No code changes required.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────────────

STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")

# Local
LOCAL_UPLOAD_DIR = Path(os.getenv("LOCAL_UPLOAD_DIR", "uploads/animal-photos"))

# S3  (only read when STORAGE_BACKEND=s3)
S3_BUCKET: str = os.getenv("S3_BUCKET", "")
S3_REGION: str = os.getenv("S3_REGION", "eu-west-1")
S3_PREFIX: str = os.getenv("S3_PREFIX", "animal-photos/")
S3_BASE_URL: str = os.getenv("S3_BASE_URL", "")   # e.g. https://cdn.ndic.ng
S3_PRESIGN_TTL: int = int(os.getenv("S3_PRESIGN_TTL", "3600"))  # seconds

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB


# ── Internal helpers ──────────────────────────────────────────────────────────

def _s3_client():
    """Return a boto3 S3 client. Raises RuntimeError if boto3 not installed."""
    try:
        import boto3  # type: ignore
        return boto3.client("s3", region_name=S3_REGION)
    except ImportError as exc:
        raise RuntimeError(
            "boto3 not installed. Run: pip install boto3"
        ) from exc


def _ext(filename: str, content_type: str) -> str:
    """Derive safe file extension from filename or content type."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/heic": "heic",
        "image/heif": "heif",
    }.get(content_type, "jpg")


# ── Public API ────────────────────────────────────────────────────────────────

async def save_photo(
    content: bytes,
    filename: str,
    content_type: str,
    animal_id: str,
) -> dict:
    """
    Persist photo bytes and return a storage metadata dict:
      {
        storage_key:    str   — unique path/key to pass to get_photo_url() and delete_photo()
        filename:       str
        content_type:   str
        file_size_bytes: int
        url:            str   — immediately-usable serving URL
      }

    Raises:
      ValueError  — unsupported content type or file too large
      RuntimeError — S3 not configured / boto3 not installed
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported content type '{content_type}'. "
            f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}"
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large ({len(content):,} bytes). "
            f"Maximum allowed: {MAX_FILE_SIZE_BYTES:,} bytes."
        )

    unique_name = f"{animal_id}/{uuid.uuid4().hex}.{_ext(filename, content_type)}"

    if STORAGE_BACKEND == "s3":
        return await _save_s3(content, unique_name, filename, content_type)
    else:
        return _save_local(content, unique_name, filename, content_type)


def get_photo_url(storage_key: str) -> str:
    """
    Return a URL that serves the photo.
    Local: a static path under /uploads.
    S3:    a pre-signed URL (valid for S3_PRESIGN_TTL seconds).
    """
    if STORAGE_BACKEND == "s3":
        s3 = _s3_client()
        full_key = storage_key if storage_key.startswith(S3_PREFIX) else f"{S3_PREFIX}{storage_key}"
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": full_key},
            ExpiresIn=S3_PRESIGN_TTL,
        )
    return f"/uploads/animal-photos/{storage_key}"


async def delete_photo(storage_key: str) -> None:
    """Remove a photo from storage. Silent no-op if file not found."""
    if STORAGE_BACKEND == "s3":
        s3 = _s3_client()
        full_key = storage_key if storage_key.startswith(S3_PREFIX) else f"{S3_PREFIX}{storage_key}"
        s3.delete_object(Bucket=S3_BUCKET, Key=full_key)
    else:
        dest = LOCAL_UPLOAD_DIR / storage_key
        if dest.exists():
            dest.unlink()


# ── Backend implementations ───────────────────────────────────────────────────

def _save_local(
    content: bytes,
    unique_name: str,
    filename: str,
    content_type: str,
) -> dict:
    dest = LOCAL_UPLOAD_DIR / unique_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return {
        "storage_key": unique_name,
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": len(content),
        "url": f"/uploads/animal-photos/{unique_name}",
    }


async def _save_s3(
    content: bytes,
    unique_name: str,
    filename: str,
    content_type: str,
) -> dict:
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET environment variable is not set.")
    s3 = _s3_client()
    key = f"{S3_PREFIX}{unique_name}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=content_type,
        ContentDisposition=f'inline; filename="{filename}"',
    )
    if S3_BASE_URL:
        url = f"{S3_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{key}"
    return {
        "storage_key": key,
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": len(content),
        "url": url,
    }
