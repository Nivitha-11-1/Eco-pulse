import os
import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")

    print("API key:", "PRESENT" if api_key else "MISSING")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Reply only with JSON: {\"ok\": true}"
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    print("Sending request to Gemini...")

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        print("HTTP:", response.status_code)
        print("Response:")
        print(response.text[:3000])

    except Exception as e:
        print("ERROR:", type(e).__name__)
        print(str(e))


if __name__ == "__main__":
    main()
