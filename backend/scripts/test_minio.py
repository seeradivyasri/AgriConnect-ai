import os
import sys
import boto3
from dotenv import find_dotenv, load_dotenv

def main():
    load_dotenv(find_dotenv(usecwd=True))
    
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    bucket = os.getenv("MINIO_BUCKET")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    
    # Boto3 expects the endpoint to include the protocol scheme
    scheme = "https" if secure else "http"
    endpoint_url = f"{scheme}://{endpoint}"
    
    print(f"Connecting to MinIO at {endpoint_url}...")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1" # MinIO defaults to us-east-1
    )
    
    try:
        # 1. Upload "hello" bytes
        s3_client.put_object(
            Bucket=bucket,
            Key="test-file.txt",
            Body=b"hello"
        )
        print("Successfully uploaded 'test-file.txt' to bucket.")
        
        # 2. Read it back
        response = s3_client.get_object(Bucket=bucket, Key="test-file.txt")
        content = response['Body'].read()
        
        if content == b"hello":
            print("MinIO OK")
            sys.exit(0)
        else:
            print(f"Error: Content mismatch. Expected b'hello', got {content}")
            sys.exit(1)
            
    except Exception as e:
        print(f"MinIO Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
