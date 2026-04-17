# PATH: /home/lumoura/trinis_ai/trinis/app/services/storage.py
"""
MinIO storage service.

Provides a simple interface to store and retrieve processed product images.
Uses the S3-compatible MinIO API via boto3.
"""
import io
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

BUCKET_NAME = "productsync-images"


@lru_cache
def _get_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint_url,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket_exists():
    """Create the images bucket if it doesn't exist."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=BUCKET_NAME)
    except ClientError:
        client.create_bucket(Bucket=BUCKET_NAME)
        # Set public read policy for product images
        client.put_bucket_policy(
            Bucket=BUCKET_NAME,
            Policy=f'''{{
                "Version": "2012-10-17",
                "Statement": [{{
                    "Effect": "Allow",
                    "Principal": {{"AWS": ["*"]}},
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::{BUCKET_NAME}/*"]
                }}]
            }}'''
        )


def upload_image(
    image_bytes: bytes,
    tenant_id: str,
    ean: str,
    index: int = 0,
) -> str:
    """
    Upload a processed product image to MinIO.
    Returns the object key.
    """
    ensure_bucket_exists()
    client = _get_client()

    key = f"{tenant_id}/{ean}/{ean}_{index}.png"

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )

    return key


def get_image_url(key: str) -> str:
    """Get a public URL for a stored image."""
    settings = get_settings()
    return f"{settings.minio_endpoint_url}/{BUCKET_NAME}/{key}"


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Get a presigned URL for private access (expires in seconds)."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


def download_image(key: str) -> bytes:
    """Download an image from MinIO as bytes."""
    client = _get_client()
    response = client.get_object(Bucket=BUCKET_NAME, Key=key)
    return response["Body"].read()


def delete_image(key: str) -> bool:
    """Delete an image from MinIO."""
    try:
        client = _get_client()
        client.delete_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except Exception:
        return False


def list_product_images(tenant_id: str, ean: str) -> list[str]:
    """List all image keys for a product."""
    client = _get_client()
    prefix = f"{tenant_id}/{ean}/"
    response = client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]