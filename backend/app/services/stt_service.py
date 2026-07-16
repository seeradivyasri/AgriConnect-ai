import io
import asyncio

from app.services import llm_gateway

async def transcribe_audio(audio_bytes: bytes, language: str = "te") -> str:
    # Use Groq API instead of local whisper
    transcript = await llm_gateway.transcribe_audio(audio_bytes, language)
    
    if not transcript:
        raise ValueError("Empty or unreadable audio")
        
    return transcript

async def extract_listing_intent(transcript: str) -> dict:
    # A simple wrapper that passes the parsed text into the LLM Gateway
    return await llm_gateway.extract_listing_intent(transcript)
