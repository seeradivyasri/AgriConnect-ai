import pytest
from unittest.mock import AsyncMock
from app.services.llm_gateway import generate_negotiation_response, extract_listing_intent, smart_shopper_chat
import re

# 1. UNIT tests (no real Groq API call — mock _call_groq):

@pytest.mark.asyncio
async def test_generate_negotiation_response_mock(mocker):
    # Mock _call_groq directly in the llm_gateway module
    mock_call = mocker.patch("app.services.llm_gateway._call_groq", new_callable=AsyncMock)
    mock_call.return_value = "This is a mocked response."
    
    decision = {"action": "ACCEPT", "final_price": 46.56}
    response = await generate_negotiation_response(decision, language="en")
    
    assert response == "This is a mocked response."
    mock_call.assert_called_once()
    args, kwargs = mock_call.call_args
    assert "46.56" in kwargs["prompt"]

@pytest.mark.asyncio
async def test_extract_listing_intent_success_mock(mocker):
    mock_call = mocker.patch("app.services.llm_gateway._call_groq", new_callable=AsyncMock)
    mock_call.return_value = '{"produce_name":"Onions","quantity":50,"unit":"kg","confidence":0.95}'
    
    result = await extract_listing_intent("I have 50 kg onions")
    assert result["produce_name"] == "Onions"
    assert result["quantity"] == 50
    assert result["unit"] == "kg"
    mock_call.assert_called_once()

@pytest.mark.asyncio
async def test_extract_listing_intent_garbage_mock(mocker):
    mock_call = mocker.patch("app.services.llm_gateway._call_groq", new_callable=AsyncMock)
    mock_call.return_value = "not json at all"
    
    result = await extract_listing_intent("Hello!")
    assert result == {"confidence": 0.0}
    mock_call.assert_called_once()

# 2. INTEGRATION tests (marked @pytest.mark.integration — real Groq API):

@pytest.mark.asyncio
@pytest.mark.integration
async def test_generate_negotiation_response_real():
    decision = {"action": "ACCEPT", "final_price": 46.56}
    response = await generate_negotiation_response(decision, language="en")
    
    assert response
    assert isinstance(response, str)
    assert "46.56" in response

@pytest.mark.asyncio
@pytest.mark.integration
async def test_smart_shopper_chat_real():
    history = []
    message = "what time will it be delivered?"
    catalog_context = "Tomatoes are available."
    
    response = await smart_shopper_chat(message, history, catalog_context)
    
    # Assert response does NOT match regex r"\d+\s*(hour|minute|day)"
    match = re.search(r"\d+\s*(hour|minute|day)", response, re.IGNORECASE)
    assert match is None, f"Response illegally promised a delivery time: {response}"

@pytest.mark.asyncio
@pytest.mark.integration
async def test_extract_listing_intent_real():
    result = await extract_listing_intent("I have 100 kg of fresh mangoes")
    
    assert isinstance(result, dict)
    assert "mangoes" in str(result.get("produce_name")).lower()
    assert result.get("quantity") == 100
    assert result.get("unit") == "kg"
