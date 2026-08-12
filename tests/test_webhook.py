import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from main import app, get_session, TicketMapping, ParsedIssue

from sqlalchemy.pool import StaticPool

# In-memory SQLite DB for testing
sqlite_url = "sqlite://"
test_engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

def override_get_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

@patch("main.parse_feedback_with_llm")
@patch("main.create_github_issue")
def test_inbound_whatsapp_webhook(mock_create_issue, mock_parse_llm):
    # Mock LLM response
    mock_parse_llm.return_value = ParsedIssue(
        selected_repo="customer-feedback-agent-demo-repo",
        title="Button is not clickable on checkout page",
        description="User unable to click pay button on checkout",
        priority="High"
    )

    # Mock GitHub issue creation returning issue number 42
    mock_create_issue.return_value = 42

    response = client.post(
        "/webhook/whatsapp",
        data={
            "From": "whatsapp:+1234567890",
            "Body": "Button is broken on checkout page"
        }
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Response><Message>" in response.text
    assert "Issue #42" in response.text

    # Verify DB persistence
    with Session(test_engine) as session:
        mapping = session.exec(select(TicketMapping)).first()
        assert mapping is not None
        assert mapping.whatsapp_number == "whatsapp:+1234567890"
        assert mapping.github_issue_id == 42
        assert mapping.repo_name == "customer-feedback-agent-demo-repo"
        assert mapping.issue_title == "Button is not clickable on checkout page"

@patch("main.send_whatsapp_notification")
def test_github_webhook_assigned(mock_send_whatsapp):
    # Seed DB with ticket mapping
    with Session(test_engine) as session:
        mapping = TicketMapping(
            whatsapp_number="whatsapp:+1234567890",
            github_issue_id=101,
            repo_name="backend-api",
            issue_title="500 Internal Server Error on /login"
        )
        session.add(mapping)
        session.commit()

    mock_send_whatsapp.return_value = True

    payload = {
        "action": "assigned",
        "issue": {"number": 101},
        "repository": {"name": "backend-api"},
        "assignee": {"login": "alice_dev"}
    }

    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "processed", "action": "assigned"}

    # Verify Twilio notification helper was called
    mock_send_whatsapp.assert_called_once()
    call_kwargs = mock_send_whatsapp.call_args.kwargs
    assert call_kwargs["to_number"] == "whatsapp:+1234567890"
    assert "alice_dev" in call_kwargs["message_text"]
    assert "Issue #101" in call_kwargs["message_text"]

@patch("main.send_whatsapp_notification")
def test_github_webhook_closed(mock_send_whatsapp):
    # Seed DB with ticket mapping
    with Session(test_engine) as session:
        mapping = TicketMapping(
            whatsapp_number="whatsapp:+1234567890",
            github_issue_id=202,
            repo_name="mobile-app",
            issue_title="Push notifications not working on iOS 18"
        )
        session.add(mapping)
        session.commit()

    mock_send_whatsapp.return_value = True

    payload = {
        "action": "closed",
        "issue": {"number": 202},
        "repository": {"name": "mobile-app"}
    }

    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "processed", "action": "closed"}

    mock_send_whatsapp.assert_called_once()
    call_kwargs = mock_send_whatsapp.call_args.kwargs
    assert call_kwargs["to_number"] == "whatsapp:+1234567890"
    assert "completed and resolved" in call_kwargs["message_text"]

def test_github_webhook_untracked():
    payload = {
        "action": "assigned",
        "issue": {"number": 999},
        "repository": {"name": "frontend-app"}
    }
    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "issue not tracked"}
