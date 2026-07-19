"""Object-storage layout and access helpers (research R9/R10).

Key scheme:
  projects/{project_id}/surveys/{survey_id}/source/{filename}
  projects/{project_id}/surveys/{survey_id}/runs/{run_id}/{artifact}

Run prefixes are append-only: a processing run may only ever write inside its
own run prefix (or the survey's source/ prefix during relocation), which makes
cross-survey mutation structurally impossible (FR-011/FR-013, SC-007).
"""

import hashlib
import os
from pathlib import Path

import boto3
from botocore.client import Config


def _client(endpoint: str):
    from django.conf import settings

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def internal_client():
    from django.conf import settings

    return _client(settings.S3_ENDPOINT)


def public_client():
    """Client whose presigned URLs are reachable from the user's browser."""
    from django.conf import settings

    return _client(settings.S3_PUBLIC_ENDPOINT)


def source_key(project_id, survey_id, filename: str) -> str:
    return f"projects/{project_id}/surveys/{survey_id}/source/{filename}"


def run_prefix(project_id, survey_id, run_id) -> str:
    return f"projects/{project_id}/surveys/{survey_id}/runs/{run_id}/"


def run_key(project_id, survey_id, run_id, artifact_name: str) -> str:
    return run_prefix(project_id, survey_id, run_id) + artifact_name


def assert_key_within_survey(key: str, project_id, survey_id) -> None:
    """Guard used by every pipeline write (T045)."""
    allowed = f"projects/{project_id}/surveys/{survey_id}/"
    if not key.startswith(allowed):
        raise AssertionError(f"storage write outside survey prefix: {key}")


def copy_object(src_key: str, dst_key: str) -> None:
    """Server-side copy; boto3 transparently uses multipart for large objects."""
    from django.conf import settings

    internal_client().copy(
        {"Bucket": settings.S3_BUCKET, "Key": src_key}, settings.S3_BUCKET, dst_key
    )


def delete_object(key: str) -> None:
    from django.conf import settings

    internal_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)


def object_size(key: str) -> int:
    from django.conf import settings

    head = internal_client().head_object(Bucket=settings.S3_BUCKET, Key=key)
    return head["ContentLength"]


def download_to(key: str, dest: Path) -> Path:
    from django.conf import settings

    dest.parent.mkdir(parents=True, exist_ok=True)
    internal_client().download_file(settings.S3_BUCKET, key, str(dest))
    return dest


def upload_file(path: Path, key: str) -> None:
    from django.conf import settings

    internal_client().upload_file(str(path), settings.S3_BUCKET, key)


def presign_get(key: str, public: bool = True) -> str:
    """Short-lived GET URL; range requests remain supported (COG/COPC readers)."""
    from django.conf import settings

    client = public_client() if public else internal_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=settings.PRESIGN_EXPIRY_SECONDS,
    )


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def scratch_dir() -> Path:
    base = Path(os.environ.get("PIPELINE_SCRATCH", "/scratch"))
    if not base.exists():
        import tempfile

        base = Path(tempfile.gettempdir())
    return base
