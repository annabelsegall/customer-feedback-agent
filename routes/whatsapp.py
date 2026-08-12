from typing import Optional
from fastapi import APIRouter, Form, Depends
from sqlmodel import Session

from config import AVAILABLE_REPOS
from database import get_session, TicketMapping
from llm import parse_feedback_with_llm
from twilio_service import fetch_twilio_media, build_twiml_response
from github_service import create_github_issue

router = APIRouter()

@router.post("/webhook/whatsapp")
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
