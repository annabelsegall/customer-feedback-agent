import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG_OR_USER = os.getenv("GITHUB_ORG_OR_USER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

import json

# Parse AVAILABLE_REPOS from environment variable or fallback to default single repo
raw_repos = os.getenv("AVAILABLE_REPOS", "customer-feedback-agent-demo-repo")

if raw_repos.startswith("{"):
    try:
        AVAILABLE_REPOS = json.loads(raw_repos)
    except Exception:
        AVAILABLE_REPOS = {"customer-feedback-agent-demo-repo": "General repository for feedback, feature requests, and bug reports."}
else:
    repo_list = [r.strip() for r in raw_repos.split(",") if r.strip()]
    AVAILABLE_REPOS = {repo: "General repository for feedback, feature requests, and bug reports." for repo in repo_list}
