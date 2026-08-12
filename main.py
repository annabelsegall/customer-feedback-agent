import os
import httpx
from typing import Optional, Generator
from fastapi import FastAPI, Request, Response, Form, Depends
from sqlmodel import Field, SQLModel, Session, create_engine, select
from github import Github, GithubException
from twilio.rest import Client
from google import genai
from google.genai import types
from pydantic import BaseModel

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER,
    GITHUB_TOKEN,
    GITHUB_ORG_OR_USER,
    GEMINI_API_KEY,
    AVAILABLE_REPOS,
)

# SQLModel DB setup
class TicketMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    whatsapp_number: str = Field(index=True)
    github_issue_id: int = Field(index=True)
    repo_name: str
    issue_title: str

sqlite_url = "sqlite:///database.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def get_twilio_client() -> Optional[Client]:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return None

def get_github_client() -> Optional[Github]:
    if GITHUB_TOKEN:
        return Github(GITHUB_TOKEN)
    return None

def get_gemini_client() -> Optional[genai.Client]:
    if GEMINI_API_KEY:
        return genai.Client(api_key=GEMINI_API_KEY)
    return None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="WhatsApp <-> GitHub Issue Bridge", lifespan=lifespan)

class ParsedIssue(BaseModel):
    selected_repo: str
    title: str
    description: str
    priority: str

def parse_feedback_with_llm(
    user_message: Optional[str] = "",
    audio_bytes: Optional[bytes] = None,
    audio_mime_type: Optional[str] = None
) -> ParsedIssue:
    gemini_client = get_gemini_client()
    msg_text = user_message or ""
    if not gemini_client:
        # Fallback default if API key is not configured
        return ParsedIssue(
            selected_repo=list(AVAILABLE_REPOS.keys())[0],
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

@app.post("/webhook/whatsapp")
async def inbound_whatsapp(
    From: str = Form(...),
    Body: Optional[str] = Form(""),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    NumMedia: Optional[str] = Form("0"),
    session: Session = Depends(get_session)
):
    user_number = From
    user_message = Body or ""

    audio_bytes = None
    if MediaUrl0:
        try:
            auth = None
            if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            async with httpx.AsyncClient() as client:
                res = await client.get(MediaUrl0, auth=auth, follow_redirects=True)
                if res.status_code == 200:
                    audio_bytes = res.content
        except Exception as e:
            print(f"Error fetching Twilio media attachment: {e}")

    parsed = parse_feedback_with_llm(
        user_message=user_message,
        audio_bytes=audio_bytes,
        audio_mime_type=MediaContentType0
    )
    target_repo_name = (
        parsed.selected_repo
        if parsed.selected_repo in AVAILABLE_REPOS
        else list(AVAILABLE_REPOS.keys())[0]
    )

    if "/" in target_repo_name:
        full_repo_path = target_repo_name
    else:
        full_repo_path = f"{GITHUB_ORG_OR_USER}/{target_repo_name}" if GITHUB_ORG_OR_USER else target_repo_name

    gh_client = get_github_client()
    
    issue_number = 1
    if gh_client:
        try:
            repo = gh_client.get_repo(full_repo_path)
            issue_body = (
                f"{parsed.description}\n\n---\n"
                f"**Submitted via:** WhatsApp\n"
                f"**Priority:** {parsed.priority}"
            )
            
            # Create issue safely with label fallback
            labels_to_apply = []
            if parsed.priority:
                priority_label = parsed.priority.lower()
                try:
                    labels_to_apply.append(priority_label)
                    issue = repo.create_issue(title=parsed.title, body=issue_body, labels=labels_to_apply)
                except GithubException:
                    # Fallback without labels if label doesn't exist on target repo
                    issue = repo.create_issue(title=parsed.title, body=issue_body)
            else:
                issue = repo.create_issue(title=parsed.title, body=issue_body)
            
            issue_number = issue.number
        except Exception as e:
            # Safe fallback logging for standalone local testing
            print(f"Error creating GitHub issue: {e}")

    mapping = TicketMapping(
        whatsapp_number=user_number,
        github_issue_id=issue_number,
        repo_name=target_repo_name,
        issue_title=parsed.title
    )
    session.add(mapping)
    session.commit()

    response_text = (
        f"Your request has been logged as Issue #{issue_number} in `{target_repo_name}`!\n\n"
        f"*Title:* {parsed.title}"
    )
    twiml_xml = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>{response_text}</Message></Response>"
    return Response(
        content=twiml_xml,
        media_type="application/xml"
    )

@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    payload = await request.json()
    action = payload.get("action")
    issue_data = payload.get("issue")

    if not issue_data:
        return {"status": "ignored"}

    issue_id = issue_data.get("number")
    repo_name = payload.get("repository", {}).get("name")

    statement = select(TicketMapping).where(
        TicketMapping.github_issue_id == issue_id,
        TicketMapping.repo_name == repo_name
    )
    mapping = session.exec(statement).first()

    if not mapping:
        return {"status": "issue not tracked"}

    notification_text = None

    if action == "assigned":
        assignee_login = payload.get("assignee", {}).get("login", "An engineer")
        notification_text = (
            f"Update on your request: *{assignee_login}* has picked up Issue #{issue_id} "
            f"('{mapping.issue_title}') and is working on it!"
        )
    elif action == "closed":
        notification_text = (
            f"Good news! Your request regarding *'{mapping.issue_title}'* (Issue #{issue_id}) "
            f"has been completed and resolved!"
        )

    if notification_text:
        twilio_client = get_twilio_client()
        if twilio_client:
            try:
                twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body=notification_text,
                    to=mapping.whatsapp_number
                )
            except Exception as e:
                print(f"Error sending Twilio WhatsApp notification: {e}")
                return {"status": "processed", "warning": f"Twilio notification failed: {e}"}

    return {"status": "processed", "action": action}
