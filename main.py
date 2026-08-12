from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import create_db_and_tables, get_session, TicketMapping
from llm import parse_feedback_with_llm, ParsedIssue, get_gemini_client
from twilio_service import send_whatsapp_notification, fetch_twilio_media, get_twilio_client
from github_service import create_github_issue, get_github_client

from routes.whatsapp import router as whatsapp_router
from routes.github import router as github_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="WhatsApp <-> GitHub Issue Bridge", lifespan=lifespan)

# Register route handlers
app.include_router(whatsapp_router)
app.include_router(github_router)
