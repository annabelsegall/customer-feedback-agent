# WhatsApp to GitHub Issues AI Bridge

An automated, event-driven AI agent bridge between Twilio WhatsApp and GitHub Issues powered by **FastAPI**, **Google Gemini 3.6 Flash** (`google-genai`), **SQLModel**, **PyGithub**, and **Twilio**.

---

## 1. Architecture Overview

### Inbound Loop (WhatsApp → GitHub)
1. **User Message**: Customer sends feature request or bug report via WhatsApp.
2. **Twilio Webhook**: Twilio forwards message payload to `POST /webhook/whatsapp`.
3. **Gemini Intent Routing**: Google Gemini 3.6 Flash classifies the issue topic, selects the target repository (`frontend-app`, `backend-api`, `mobile-app`), and generates title, description, and priority using structured JSON outputs.
4. **GitHub Issue Creation**: Issue created in target GitHub repository via PyGithub.
5. **Database Mapping**: DB record saved linking `whatsapp_number`, `github_issue_id`, `repo_name`, and `issue_title`.
6. **User Confirmation**: TwiML XML response sent to WhatsApp confirming issue creation with ID.

### Outbound Loop (GitHub → WhatsApp)
1. **GitHub Issue Event**: Engineer assigns or closes an issue.
2. **GitHub Webhook**: GitHub sends JSON payload to `POST /webhook/github`.
3. **Database Lookup**: Endpoint matches `github_issue_id` and `repo_name` in SQLite database.
4. **Twilio Notification**: Automated WhatsApp status update sent back to original reporter.

---

## 2. Environment Variables

Create a `.env` file from `.env.example`:

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_ORG_OR_USER=my-org-name

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 3. Setup & Installation

### Setup Virtual Environment & Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Running the Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn main:app --reload --port 8000
```

Access Swagger API docs at `http://localhost:8000/docs`.

---

## 5. Webhook Setup & Ngrok Tunneling

1. Start tunneling local port 8000:
   ```bash
   ngrok http 8000
   ```
2. Configure **Twilio WhatsApp Sandbox**:
   - Inbound Webhook URL: `https://<your_ngrok_subdomain>.ngrok-free.app/webhook/whatsapp` (HTTP POST)
3. Configure **GitHub Repository Webhooks**:
   - Payload URL: `https://<your_ngrok_subdomain>.ngrok-free.app/webhook/github`
   - Content type: `application/json`
   - Events: Select **Issues** events.

---

## 6. Running Tests

Run the unit and integration test suite:

```bash
pytest tests/
```
