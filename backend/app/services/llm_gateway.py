import json
import structlog
from typing import List, Dict, Any
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from fastapi import HTTPException

from app.config import settings

logger = structlog.get_logger()

# 1. Module-level client instance (Reused)
_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY, 
    base_url=settings.GROQ_BASE_URL
)

# 2. System Prompts
NEGOTIATION_SYSTEM_PROMPT = """
You are an agricultural negotiation assistant. Your job is to communicate a pricing decision to a farmer.
Strict Rules:
- You must use the exact price provided in the JSON decision. Do not invent or negotiate numbers.
- Make absolutely no promises about logistics or delivery.
- Your response MUST be exactly ONE highly efficient, impactful, and polite sentence. Do not ramble.
- If the language is "te", you MUST respond entirely in the Telugu script.
- If the decision action is "REJECT", you must concisely explain in that single sentence that the requested price is too high for the current market and a deal cannot be made.
- If the decision JSON contains a 'produce_name', you MUST naturally weave the name of the crop (e.g. 'క్యారెట్లు', 'టమాటాలు') into your sentence instead of using generic words like 'పంట' (crop).
- If round_number is 2, you MUST warn the farmer in your sentence that their next offer will be the final round.
- If round_number is 3, you MUST state in your sentence that this is your final absolute best offer.
"""

SMART_SHOPPER_SYSTEM_PROMPT = """
You are a helpful Smart Shopper assistant for an agricultural marketplace.
Strict Rules:
- You must never promise a specific delivery time.
- You must never guarantee stock availability.
- You must never negotiate the price of an item.
"""

# 3. Robust API Wrapper
@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(min=1, max=4),
    reraise=False
)
async def _call_groq(prompt: str, system: str, temperature: float = 0.3, max_tokens: int = 500, messages: List[Dict[str, str]] = None) -> str:
    """
    Internal wrapper to call Groq API with retries.
    """
    try:
        # If a raw messages array is passed (for chat history), prepend the system prompt
        if messages:
            api_messages = [{"role": "system", "content": system}] + messages
        else:
            api_messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            
        response = await _client.chat.completions.create(
            model=settings.GROQ_TEXT_MODEL,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("groq_api_error", error=str(e))
        raise HTTPException(status_code=503, detail="LLM unavailable")

async def transcribe_audio(audio_bytes: bytes, language: str = "te") -> str:
    """
    Transcribe audio using Groq's Whisper API.
    """
    try:
        response = await _client.audio.transcriptions.create(
            file=("audio.webm", audio_bytes),
            model="whisper-large-v3",
            language=language
        )
        return response.text.strip()
    except Exception as e:
        logger.error("groq_stt_error", error=str(e))
        raise ValueError("Empty or unreadable audio")

# 4. Service Functions

async def generate_negotiation_response(decision: dict, language: str = "en") -> str:
    """
    Converts a math decision into a natural language response.
    """
    prompt = f"Convert this decision to a natural message. Language: {language}\n{str(decision)}"
    return await _call_groq(
        prompt=prompt,
        system=NEGOTIATION_SYSTEM_PROMPT,
        temperature=0.2
    )

async def extract_listing_intent(transcript: str) -> dict:
    """
    Extracts produce listing details from a voice transcript.
    """
    system_prompt = (
        "Extract produce listing intent from the text. Return ONLY a valid JSON object "
        "with exactly these keys: {produce_name, quantity, unit, confidence, confirmation_message_te}. "
        "The produce_name MUST ALWAYS be translated to a standard English noun (e.g. 'Tomato', 'Carrot', 'Onion'). "
        "The confirmation_message_te must be a polite conversational Telugu phrase asking the farmer to confirm their listing, "
        "for example: 'మీరు 50 కిలోల ఉల్లిపాయలు అమ్మాలనుకుంటున్నారా?' (Do you want to sell 50 kg of Onions?). "
        "DO NOT output any conversational text, explanation, or markdown formatting. ONLY raw JSON."
    )
    
    raw_response = await _call_groq(
        prompt=transcript,
        system=system_prompt,
        temperature=0.0
    )
    
    try:
        # Strip markdown fences if the LLM adds them
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
            
        return json.loads(clean_json.strip())
    except Exception as e:
        logger.warning("intent_extraction_failed", error=str(e), raw_response=raw_response)
        return {"confidence": 0.0}

async def smart_shopper_chat(message: str, history: List[Dict[str, str]], catalog_context: str) -> str:
    """
    Conversational assistant for customers.
    """
    # Build system prompt with context
    system = f"{SMART_SHOPPER_SYSTEM_PROMPT}\n\nCatalog Context:\n{catalog_context}"
    
    # Append the newest message to history
    full_history = history.copy()
    full_history.append({"role": "user", "content": message})
    
    return await _call_groq(
        prompt="", # Prompt is handled via the full_history messages list
        system=system,
        temperature=0.2,
        messages=full_history
    )

async def estimate_produce_price(produce_name: str) -> str:
    """
    Estimates a realistic wholesale market price (INR per kg) for a new produce in India.
    Returns only a numeric string.
    """
    system_prompt = (
        "You are an expert Indian agricultural pricing AI. "
        "Estimate the current average wholesale market price in INR per kg for the requested vegetable/fruit. "
        "Return ONLY a single numeric value (e.g., '25', '45', '120'). No symbols, no text."
    )
    
    response = await _call_groq(
        prompt=f"What is the wholesale price of {produce_name} in INR per kg?",
        system=system_prompt,
        temperature=0.1,
        max_tokens=10
    )
    
    # Strip any non-numeric chars just in case
    clean_price = "".join(c for c in response if c.isdigit() or c == '.')
    return clean_price if clean_price else "40"
