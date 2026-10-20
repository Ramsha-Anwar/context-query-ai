import json
from google import genai
from google.genai import types
from app.config import settings

class AiUnavailable(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(detail)
        self.kind = kind

_client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=15_000))

def hub_insights(content: str) -> tuple[str | None, list[str]]:
    try:
        r = _client.models.generate_content(
            model=settings.GEMINI_MODEL, 
            contents=f"<context>{content}</context>",
            config=types.GenerateContentConfig(
                system_instruction='Reply with JSON only: {"summary": "at most 2 sentences", "questions": ["3 questions"]}',
                temperature=0.2, max_output_tokens=1024, response_mime_type="application/json"
            )
        )
        d = json.loads(r.text)
        return str(d.get("summary", ""))[:500], [str(q)[:200] for q in d.get("questions", [])][:3]
    except Exception:
        return None, []