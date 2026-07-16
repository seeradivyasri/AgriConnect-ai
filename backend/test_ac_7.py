import asyncio
import boto3
import uuid
from botocore.client import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.models.produce import Listing
from app.models.user import User
from app.routers.listings import router
from app.utils.dependencies import require_farmer
from app.config import settings

app = FastAPI()
app.include_router(router)

async def main():
    listing = Listing(
        listing_id=uuid.uuid4(),
        farmer_id=uuid.uuid4(),
        produce_id=uuid.uuid4(),
        quantity=50
    )
    
    print(f"Mock listing: {listing.listing_id} owned by farmer: {listing.farmer_id}")
    
    # Override require_farmer
    async def override_require_farmer():
        return User(
            user_id=listing.farmer_id,
            phone="+919999999999",
            name="Dummy Farmer",
            role="farmer",
            verified=True
        )
        
    # Override get_db to return a mock session that just returns this listing
    class MockResult:
        def scalar_one_or_none(self):
            return listing
            
    class MockSession:
        async def execute(self, *args, **kwargs):
            return MockResult()
        async def commit(self):
            pass
            
    async def override_get_db():
        yield MockSession()

    app.dependency_overrides[require_farmer] = override_require_farmer
    app.dependency_overrides[get_db] = override_get_db
    
    endpoint = settings.MINIO_ENDPOINT
    if not endpoint.startswith("http"):
        scheme = "https" if settings.MINIO_SECURE else "http"
        endpoint = f"{scheme}://{endpoint}"
        
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        use_ssl=settings.MINIO_SECURE,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Ensure bucket exists
    try:
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.MINIO_BUCKET)
        print(f"Created bucket {settings.MINIO_BUCKET}")

    client = TestClient(app)
    
    print("\n--- Testing 413 Size Check ---")
    # Create 6MB dummy file
    big_file = b"0" * (6 * 1024 * 1024)
    resp_413 = client.post(f"/api/v1/listings/{listing.listing_id}/photo", files={"photo": ("big.jpg", big_file, "image/jpeg")})
    print("Status:", resp_413.status_code)
    print("Response:", resp_413.json())
    
    print("\n--- Testing Successful Upload & Vision Grading ---")
    small_file = b"fake image bytes"
    resp_200 = client.post(f"/api/v1/listings/{listing.listing_id}/photo", files={"photo": ("small.jpg", small_file, "image/jpeg")})
    print("Status:", resp_200.status_code)
    resp_data = resp_200.json()
    print("Response:", resp_data)
    
    print("\n--- Checking MinIO Console ---")
    if "photo_url" in resp_data:
        key = resp_data["photo_url"]
        try:
            s3.head_object(Bucket=settings.MINIO_BUCKET, Key=key)
            print(f"SUCCESS: File '{key}' exists in MinIO bucket '{settings.MINIO_BUCKET}'!")
        except Exception as e:
            print(f"FAILED: File not found in MinIO. Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
