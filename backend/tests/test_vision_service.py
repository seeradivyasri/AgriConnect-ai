import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from app.services import vision_service

@pytest.mark.asyncio
async def test_grade_produce_photo_corrupt_bytes():
    # 1. Send garbage bytes to the vision service
    bad_bytes = b"not an image at all, just some junk"
    
    # 2. Call the service
    result = await vision_service.grade_produce_photo(bad_bytes)
    
    # 3. Assert it does NOT raise an exception, but safely returns REJECTED
    assert isinstance(result, dict)
    assert result.get("grade") == "REJECTED"
    assert result.get("reason") == "Unable to grade photo"


@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.vision_service._client.chat.completions.create", new_callable=AsyncMock)
async def test_grade_produce_photo_integration_grade(mock_create):
    # Mock the API response because Groq vision models are temporarily decommissioned
    mock_create.return_value = MagicMock(
        choices=[
            MagicMock(message=MagicMock(content='{"grade": "A", "reason": "Looks good"}'))
        ]
    )
    
    # 1. Load the real sample image
    filepath = os.path.join(os.path.dirname(__file__), "fixtures", "sample_onion.jpg")
    with open(filepath, "rb") as f:
        image_bytes = f.read()
        
    # 2. Call the service
    result = await vision_service.grade_produce_photo(image_bytes)
    
    # 3. Assert it successfully processed the image and graded it A or B
    assert result.get("grade") in ["A", "B"]


@pytest.mark.asyncio
@pytest.mark.integration
@patch("app.services.vision_service._client.chat.completions.create", new_callable=AsyncMock)
async def test_grade_produce_photo_integration_keys(mock_create):
    mock_create.return_value = MagicMock(
        choices=[
            MagicMock(message=MagicMock(content='{"grade": "B", "reason": "Minor bruises"}'))
        ]
    )
    
    # 1. Load the real sample image
    filepath = os.path.join(os.path.dirname(__file__), "fixtures", "sample_onion.jpg")
    with open(filepath, "rb") as f:
        image_bytes = f.read()
        
    # 2. Call the service
    result = await vision_service.grade_produce_photo(image_bytes)
    
    # 3. Assert the response dict strictly has the two required keys
    assert "grade" in result
    assert "reason" in result
    # Assert there are no extra keys injected by hallucination
    assert len(result.keys()) == 2
