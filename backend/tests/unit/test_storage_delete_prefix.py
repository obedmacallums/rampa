"""T003: delete_prefix removes everything under a prefix, nothing else."""

import uuid

import pytest
from django.conf import settings

from pipeline import storage


@pytest.fixture
def bucket_client():
    client = storage.internal_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        pytest.skip("MinIO/S3 not reachable — run against the compose stack")
    return client


def _put(client, key: str) -> None:
    client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=b"x")


def _exists(client, key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        client.head_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def test_delete_prefix_removes_only_matching_objects(bucket_client):
    root = f"test-delete-prefix/{uuid.uuid4()}"
    in_prefix = [f"{root}/a.txt", f"{root}/sub/b.txt"]
    outside_prefix = f"test-delete-prefix-other/{uuid.uuid4()}/c.txt"
    for key in [*in_prefix, outside_prefix]:
        _put(bucket_client, key)

    storage.delete_prefix(f"{root}/")

    for key in in_prefix:
        assert not _exists(bucket_client, key)
    assert _exists(bucket_client, outside_prefix)

    bucket_client.delete_object(Bucket=settings.S3_BUCKET, Key=outside_prefix)
