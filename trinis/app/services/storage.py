"""
Storage service — MinIO (S3-compatible) via boto3.
"""
import boto3
from botocore.client import Config
from app.core.config import get_settings

settings = get_settings()

def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint_url,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )

def upload_image(image_bytes: bytes, tenant_id: str, ean: str, index: int) -> str:
    """Upload image bytes to MinIO and return the object key."""
    client = _get_client()
    key = f"{tenant_id}/images/{ean}_{index}.jpg"
    client.put_object(
        Bucket=settings.aws_s3_bucket,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )
    return key
