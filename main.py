from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Form, Depends
from sqlmodel import Session, select

from config import AVAILABLE_REPOS
from database import create_db_and_tables, get_session, TicketMapping
from llm import parse_feedback_with_llm, ParsedIssue, get_gemini_client
from twilio_service import (
    fetch_twilio_media,
    send_whatsapp_notification,
    build_twiml_response,
    get_twilio_client,
)
from github_service import create_github_issue, get_github_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="WhatsApp <-> GitHub Issue Bridge", lifespan=lifespan)

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
        audio_bytes = await fetch_twilio_media(MediaUrl0)

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

    issue_number = create_github_issue(
        target_repo_name=target_repo_name,
        title=parsed.title,
        description=parsed.description,
        priority=parsed.priority
    )

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
    return build_twiml_response(response_text)

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
        success = send_whatsapp_notification(
            to_number=mapping.whatsapp_number,
            message_text=notification_text
        )
        if not success:
            return {"status": "processed", "warning": "Twilio notification failed to send"}

    return {"status": "processed", "action": action}
