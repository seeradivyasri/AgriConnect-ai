
import base64
import json
import re
from openai import AsyncOpenAI
from app.config import settings

# Initialize module-level client specifically for the Vision service
_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url=settings.GROQ_BASE_URL
)

GRADING_PROMPT = """
You are a strict agricultural inspector grading produce from a photo.
Analyze the produce and grade it based on these exact criteria:
- A = Fresh, vibrant, excellent condition
- B = Minor blemishes, slightly dull, acceptable condition
- C = Damaged, heavily bruised, poor condition
- REJECTED = Rotten, blurry, not produce, or completely unrecognizable

You MUST return your response as ONLY a valid JSON object in the exact format below, with NO other text, markdown, or explanation:
{
  "grade": "A" | "B" | "C" | "REJECTED",
  "reason": "<One short sentence explaining why>"
}
"""

async def grade_produce_photo(image_bytes: bytes) -> dict:
    try:
        # Convert bytes to base64 for the vision API
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        response = await _client.chat.completions.create(
            model=settings.GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GRADING_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # Strip away any markdown json formatting fences if the model disobeys and adds them
        clean_content = re.sub(r"^```(?:json)?|```$", "", raw_content, flags=re.MULTILINE).strip()
        
        return json.loads(clean_content)
        
    except Exception as e:
        print(f"Vision API Exception: {type(e).__name__}: {str(e)}")
        # Fallback if Groq API fails or JSON parsing fails
        return {
            "grade": "REJECTED",
            "reason": "Unable to grade photo"
        }
