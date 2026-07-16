import pytest
from app.services import stt_service
import os

@pytest.mark.asyncio
async def test_transcribe_audio_valid():
    # 1. Read the valid WAV file
    filepath = os.path.join(os.path.dirname(__file__), "fixtures", "english_onions.wav")
    with open(filepath, "rb") as f:
        audio_bytes = f.read()
    
    # 2. Call the service (Using real Whisper AI via whisper_manager)
    # We pass language="en" because our TTS generated an english voice, not telugu
    transcript = await stt_service.transcribe_audio(audio_bytes, language="en")
    
    # 3. Verify it successfully transcribed something non-empty
    assert isinstance(transcript, str)
    assert len(transcript) > 0
    assert "onion" in transcript.lower()

@pytest.mark.asyncio
async def test_transcribe_audio_invalid():
    # 1. Provide invalid bytes instead of a real audio file
    invalid_bytes = b"not audio data at all"
    
    # 2. Verify it raises a ValueError when the transcript is empty/fails
    with pytest.raises(ValueError):
        await stt_service.transcribe_audio(invalid_bytes, language="en")

@pytest.mark.asyncio
async def test_extract_listing_intent_mocked(mocker):
    # 1. Mock the LLM Gateway so we don't actually hit the Groq API (Rule 8)
    mock_llm_gateway = mocker.patch("app.services.stt_service.llm_gateway.extract_listing_intent")
    mock_llm_gateway.return_value = {
        "produce_name": "Onions",
        "quantity": 50.0,
        "unit": "kg",
        "confidence": 0.99
    }
    
    # 2. Call the service
    intent = await stt_service.extract_listing_intent("I have 50 kilograms of onions")
    
    # 3. Verify it properly wraps and returns the dict
    assert intent["produce_name"] == "Onions"
    assert intent["quantity"] == 50.0
    assert intent["unit"] == "kg"
    assert intent["confidence"] == 0.99
    mock_llm_gateway.assert_called_once_with("I have 50 kilograms of onions")
