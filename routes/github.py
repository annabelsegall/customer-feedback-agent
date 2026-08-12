from fastapi import APIRouter, Request, Depends
from sqlmodel import Session, select

from database import get_session, TicketMapping
from twilio_service import send_whatsapp_notification

router = APIRouter()

@router.post("/webhook/github")
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
    comment_data = payload.get("comment")

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
    elif comment_data and action == "created":
        commenter_login = comment_data.get("user", {}).get("login", "An engineer")
        comment_body = comment_data.get("body", "").strip()
        notification_text = (
            f"New comment on your request *'{mapping.issue_title}'* (Issue #{issue_id}) "
            f"by *{commenter_login}*:\n\n\"{comment_body}\""
        )

    if notification_text:
        success = send_whatsapp_notification(
            to_number=mapping.whatsapp_number,
            message_text=notification_text
        )
        if not success:
            return {"status": "processed", "warning": "Twilio notification failed to send"}

    return {"status": "processed", "action": action}
