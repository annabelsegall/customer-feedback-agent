import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG_OR_USER = os.getenv("GITHUB_ORG_OR_USER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

AVAILABLE_REPOS = {
    "frontend-app": "UI components, dashboards, web pages, visual layout bugs.",
    "backend-api": "Database queries, payment processing, authentication, server 500 errors.",
    "mobile-app": "iOS and Android apps, push notifications, mobile UI issues."
}
