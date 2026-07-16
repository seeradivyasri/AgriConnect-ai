from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.listings import router
import os

app = FastAPI()
app.include_router(router)

client = TestClient(app)

print("\n--- AC-6.3: POST with WAV file ---")
wav_path = os.path.join("tests", "fixtures", "english_onions.wav")
with open(wav_path, "rb") as f:
    response = client.post("/api/v1/voice/transcribe", files={"audio": ("english_onions.wav", f, "audio/wav")})
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

print("\n--- AC-6.4: POST with text file (not audio) ---")
# Create a dummy text file
with open("dummy.txt", "w") as f:
    f.write("This is a text file, not an audio file.")

with open("dummy.txt", "rb") as f:
    response2 = client.post("/api/v1/voice/transcribe", files={"audio": ("dummy.txt", f, "text/plain")})
print(f"Status Code: {response2.status_code}")
print(f"Response: {response2.json()}")
