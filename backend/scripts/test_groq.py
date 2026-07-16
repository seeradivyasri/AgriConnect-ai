import asyncio
import os
import sys
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIStatusError

async def main():
    # 1. Load the .env file from the project root
    from dotenv import find_dotenv
    load_dotenv(find_dotenv(usecwd=True))

    api_key = os.getenv("GROQ_API_KEY")
    base_url = os.getenv("GROQ_BASE_URL")

    if not api_key or api_key == "your-groq-api-key-here":
        print("Error: Real GROQ_API_KEY not found in .env. Please add it first.")
        sys.exit(1)

    # 2. Create an AsyncOpenAI client targeting Groq
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    print("Sending request to Llama 3.3 70B on Groq...")
    
    try:
        # 3. Call Groq
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": "Reply with exactly the text: GROQ_OK and nothing else"}
            ],
            temperature=0.0,
            max_tokens=10
        )

        # 4. Print the response
        reply_text = response.choices[0].message.content.strip()
        print(f"Response: {reply_text}")

        # 5. Exit with code 1 if response does not contain GROQ_OK
        if "GROQ_OK" not in reply_text:
            print("Error: The string 'GROQ_OK' was not found in the response.")
            sys.exit(1)
            
        print("Success: Groq API is working perfectly.")
        sys.exit(0)

    except APIStatusError as e:
        print(f"API Call Failed with HTTP Status Code: {e.status_code}")
        try:
            print(f"Error Details: {e.response.json()}")
        except Exception:
            print(f"Error Message: {e.message}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
