import os
import requests
from django.conf import settings

def get_gemini_response(prompt, role='assistant'):
    api_key = os.getenv('GEMINI_API_KEY', getattr(settings, 'GEMINI_API_KEY', None))
    if not api_key:
        return "Gemini API key not set."

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"


    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": f"You are a helpful {role} for student mental health. {prompt}"}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini error: {e}"
