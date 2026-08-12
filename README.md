# 🤖 WhatsApp to GitHub Issues AI Bridge

> **An event-driven, multimodal AI agent bridge that converts customer WhatsApp messages and voice notes into structured GitHub Issues, providing real-time, bidirectional progress notifications back to customers.**

---

## 🌟 Executive Summary & Solutions Engineering Value

In modern B2B and customer-facing engineering teams, customer feedback and bug reports often originate in high-friction or informal channels like WhatsApp. Solutions Engineers and Support Leads spend valuable hours manually summarizing messages, identifying target code repositories, drafting GitHub tickets, and manually updating customers on progress.

The **WhatsApp to GitHub Issues AI Bridge** automates this entire lifecycle end-to-end:

* **Zero Customer Friction**: Customers submit feature requests or bug reports via WhatsApp text or **voice notes**.
* **Instant Multimodal AI Processing**: Powered by **Google Gemini 3.6 Flash**, the system transcribes voice notes, categorizes feedback, generates structured titles and descriptions, assigns priority levels, and routes tickets to designated GitHub repositories.
* **Privacy & PII Protection**: Customer phone numbers are redacted from public GitHub issues while being securely mapped in a private SQLite database.
* **Closed-Loop Customer Communication**: When engineers assign, comment on, or close a GitHub issue, automated WhatsApp notifications keep the customer informed in real time.

---

## 🚀 Key Features & Architectural Capabilities

* **🎙️ Native Voice Note & Multimodal Audio Support**: Direct integration with Gemini 3.6 Flash multimodal audio understanding to transcribe and extract intent from `.ogg` / `.mp4` / `.amr` WhatsApp voice recordings.
* **🏷️ Guaranteed Auto-Labeling**: Ensures repo labels (`whatsapp`, `High`, `Medium`, `Low`) are automatically created and attached to every GitHub issue.
* **🛡️ Privacy-First PII Handling**: Protects customer privacy by eliminating phone number leakage on GitHub issue bodies.
* **💬 Two-Way Interactive Sync**: Real-time notifications for developer comments, assignment changes, and issue resolutions.
* **🧩 Modular & Clean Codebase**: Architecture adhering to SOLID design principles (`routes/`, `llm.py`, `github_service.py`, `twilio_service.py`, `database.py`).
* **⚙️ Configurable Multi-Repo Routing**: Repositories dynamically configured via `.env` or JSON mapping.

---

## 🏗️ System Architecture & Workflow

```text
 ┌────────────────┐         ┌───────────────┐         ┌────────────────────────────────┐
 │ Customer       │         │ Twilio        │         │ FastAPI Bridge                 │
 │ WhatsApp App   ├────────►│ Webhook API   ├────────►│ /webhook/whatsapp              │
 └────────────────┘         └───────────────┘         └───────────────┬────────────────┘
                                                                      │
                                                     ┌────────────────┴────────────────┐
                                                     │ Google Gemini 3.6 Flash         │
                                                     │ Multimodal Intent & Parsing     │
                                                     └────────────────┬────────────────┘
                                                                      │
                                                     ┌────────────────▼────────────────┐
                                                     │ PyGithub & SQLite Persistence   │
                                                     │ Creates Issue & Ticket Mapping  │
                                                     └────────────────┬────────────────┘
                                                                      │
 ┌────────────────┐         ┌───────────────┐        ┌────────────────▼────────────────┐
 │ Developer /    │         │ GitHub        │        │ /webhook/github                 │
 │ GitHub Repo    ├────────►│ Webhook Event ├───────►│ Triggers Outbound WhatsApp Text │
 └────────────────┘         └───────────────┘        └─────────────────────────────────┘
```

---

## 📂 Project Structure

```text
.
├── main.py             # FastAPI entry point & lifespan management (~20 lines)
├── config.py           # Environment variables & repository mapping configuration
├── database.py         # SQLModel database engine, schemas, and session providers
├── llm.py              # Gemini 3.6 Flash multimodal parsing & audio voice note processing
├── twilio_service.py   # Twilio REST API client, media fetcher & TwiML response builder
├── github_service.py   # PyGithub issue creation & automated label management
├── routes/
│   ├── whatsapp.py     # Inbound WhatsApp webhook controller (/webhook/whatsapp)
│   └── github.py       # Outbound GitHub event webhook controller (/webhook/github)
├── tests/
│   └── test_webhook.py # Pytest integration test suite (100% pass rate)
├── .env.example         # Template for environment configuration
└── requirements.txt    # Production dependencies
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory:

```env
# 1. Twilio Credentials (from https://console.twilio.com)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# 2. GitHub Credentials (from GitHub Settings -> Developer settings -> Personal access tokens)
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_ORG_OR_USER=your_github_username_or_org

# 3. Target GitHub Repositories (comma-separated list, single repo, or JSON dictionary)
AVAILABLE_REPOS=customer-feedback-agent-demo-repo

# 4. Google Gemini API Key (from https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key
```

---

## 🛠️ Quickstart Guide

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Automated Test Suite
```bash
pytest tests/ -v
```
*Output:*
```text
tests/test_webhook.py::test_inbound_whatsapp_webhook PASSED              [ 20%]
tests/test_webhook.py::test_github_webhook_assigned PASSED               [ 40%]
tests/test_webhook.py::test_github_webhook_closed PASSED                 [ 60%]
tests/test_webhook.py::test_github_webhook_comment PASSED                [ 80%]
tests/test_webhook.py::test_github_webhook_untracked PASSED              [100%]

======================== 5 passed in 5.67s ========================
```

### 3. Launch Development Server
```bash
uvicorn main:app --reload --port 8000
```
Interactive API Documentation is available at `http://localhost:8000/docs`.

### 4. Webhook Endpoint Setup

* **Twilio WhatsApp Inbound Webhook**:
  - URL: `https://<your-domain>/webhook/whatsapp`
  - HTTP Method: `POST`
* **GitHub Repository Webhook**:
  - URL: `https://<your-domain>/webhook/github`
  - Content type: `application/json`
  - Events: `Issues`, `Issue comments`

---

## 🧪 Demonstration & Use Case Walkthrough

<video src="assets/demo.mp4" controls="controls" width="100%" style="max-height: 500px;">
  Your browser does not support the video tag. [Watch Demo Video](assets/demo.mp4)
</video>

1. **Voice Note Submission**: Customer records a voice note on WhatsApp describing a bug.
2. **Automated AI Extraction**: Gemini 3.6 Flash transcribes the audio, analyzes the technical root cause, and generates a structured GitHub issue with `High` priority.
3. **Developer Action**: An engineer comments on the GitHub issue: *"Deploying patch to staging now."*
4. **Instant Customer Update**: The customer automatically receives a WhatsApp text with the developer's update.

---

## 🛠️ Technology Stack

* **Framework**: FastAPI (Python 3.9+)
* **AI Engine**: Google Gemini 3.6 Flash (`google-genai` SDK)
* **Database & ORM**: SQLModel / SQLite
* **Integrations**: PyGithub, Twilio REST API, TwiML XML
* **Testing**: Pytest, FastAPI TestClient, Httpx
