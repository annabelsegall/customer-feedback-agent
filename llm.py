from typing import Optional
from google import genai
from google.genai import types
from pydantic import BaseModel
from config import GEMINI_API_KEY, AVAILABLE_REPOS

class ParsedIssue(BaseModel):
    selected_repo: str
    title: str
    description: str
    priority: str

def get_gemini_client() -> Optional[genai.Client]:
    if GEMINI_API_KEY:
        return genai.Client(api_key=GEMINI_API_KEY)
    return None

def parse_feedback_with_llm(
    user_message: Optional[str] = "",
    audio_bytes: Optional[bytes] = None,
    audio_mime_type: Optional[str] = None
) -> ParsedIssue:
    gemini_client = get_gemini_client()
    msg_text = user_message or ""
    if not gemini_client:
        # Fallback default if API key is not configured
        default_repo = list(AVAILABLE_REPOS.keys())[0] if AVAILABLE_REPOS else "default-repo"
        return ParsedIssue(
            selected_repo=default_repo,
            title=msg_text[:50] or "Voice Note Feedback",
            description=msg_text or "Feedback submitted via voice note.",
            priority="Medium"
        )
    
    prompt = f"""
    You are an expert Solutions Engineer routing customer feedback to engineering teams.
    Analyze the incoming customer message (which may include a voice note audio recording and/or text) and select the most appropriate target repository from this list:
    {AVAILABLE_REPOS}

    Respond ONLY with a JSON object matching this structure:
    {{
        "selected_repo": "repository_name",
        "title": "Short title summary of issue",
        "description": "Detailed description of user feedback",
        "priority": "High" or "Medium" or "Low"
    }}

    User Message Text: "{msg_text}"
    """
    
    contents = []
    if audio_bytes:
        mime = audio_mime_type or "audio/ogg"
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime)
        contents.append(audio_part)
    
    contents.append(prompt)
    
    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    return ParsedIssue.model_validate_json(response.text)
