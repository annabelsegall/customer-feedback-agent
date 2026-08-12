import os
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

app = FastAPI(title="WhatsApp <-> GitHub Issue Bridge")

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

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

class ParsedIssue(BaseModel):
    selected_repo: str
    title: str
    description: str
    priority: str

def parse_feedback_with_llm(user_message: str) -> ParsedIssue:
    gemini_client = get_gemini_client()
    if not gemini_client:
        # Fallback default if API key is not configured
        return ParsedIssue(
            selected_repo=list(AVAILABLE_REPOS.keys())[0],
            title=user_message[:50],
            description=user_message,
            priority="Medium"
        )
    
    prompt = f"""
    You are an expert Solutions Engineer routing customer feedback to engineering teams.
    Analyze the incoming message and select the most appropriate target repository from this list:
    {AVAILABLE_REPOS}

    User Message: "{user_message}"
    """
    
    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ParsedIssue,
        ),
    )
    return ParsedIssue.model_validate_json(response.text)

@app.post("/webhook/whatsapp")
async def inbound_whatsapp(
    From: str = Form(...),
    Body: str = Form(...),
    session: Session = Depends(get_session)
):
    user_number = From
    user_message = Body

    parsed = parse_feedback_with_llm(user_message)
    target_repo_name = (
        parsed.selected_repo
        if parsed.selected_repo in AVAILABLE_REPOS
        else list(AVAILABLE_REPOS.keys())[0]
    )

    full_repo_path = f"{GITHUB_ORG_OR_USER}/{target_repo_name}"
    gh_client = get_github_client()
    
    issue_number = 1
    if gh_client:
        try:
            repo = gh_client.get_repo(full_repo_path)
            issue_body = (
                f"{parsed.description}\n\n---\n"
                f"**Submitted via WhatsApp by:** {user_number}\n"
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
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=notification_text,
                to=mapping.whatsapp_number
            )

    return {"status": "processed", "action": action}
