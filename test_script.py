from fastapi.testclient import TestClient
from api.main import app

with TestClient(app) as client:
    print("Testing health...")
    r = client.get("/health")
    print(r.status_code, r.json())
    
    print("Testing predict...")
    r = client.post("/predict", json={"timestamp": "2026-06-30T10:00:00Z", "value": 12.5})
    print(r.status_code, r.json())
    
    # Send another one to verify it updates properly
    r = client.post("/predict", json={"timestamp": "2026-06-30T10:01:00Z", "value": 13.0})
    print(r.status_code, r.json())
    
    # Send an out-of-order one
    r = client.post("/predict", json={"timestamp": "2026-06-30T09:59:00Z", "value": 10.0})
    print(r.status_code, r.json())
