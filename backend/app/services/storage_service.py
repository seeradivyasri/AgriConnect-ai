import boto3
from botocore.client import Config
from app.config import settings

# Ensure endpoint has a scheme for boto3
endpoint = settings.MINIO_ENDPOINT
if not endpoint.startswith("http"):
    scheme = "https" if settings.MINIO_SECURE else "http"
    endpoint = f"{scheme}://{endpoint}"

# Initialize the MinIO (S3-compatible) client
s3_client = boto3.client(
    's3',
    endpoint_url=endpoint,
    aws_access_key_id=settings.MINIO_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_SECRET_KEY,
    use_ssl=settings.MINIO_SECURE,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1' # Required by boto3 even for local MinIO
)

def upload_file(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    s3_client.put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type
    )
    return key

def get_presigned_url(key: str, expires: int = 3600) -> str:
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.MINIO_BUCKET, 'Key': key},
        ExpiresIn=expires
    )
    return url
