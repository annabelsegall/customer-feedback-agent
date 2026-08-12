import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from main import app, get_session, TicketMapping, ParsedIssue

# In-memory SQLite DB for testing
sqlite_url = "sqlite:///:memory:"
test_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

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
@patch("main.get_github_client")
def test_inbound_whatsapp_webhook(mock_get_github, mock_parse_llm):
    # Mock LLM response
    mock_parse_llm.return_value = ParsedIssue(
        selected_repo="frontend-app",
        title="Button is not clickable on checkout page",
        description="User unable to click pay button on checkout",
        priority="High"
    )

    # Mock GitHub Client & Issue creation
    mock_gh = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 42
    mock_repo.create_issue.return_value = mock_issue
    mock_gh.get_repo.return_value = mock_repo
    mock_get_github.return_value = mock_gh

    response = client.post(
        "/webhook/whatsapp",
        data={
            "From": "whatsapp:+1234567890",
            "Body": "Button is broken on checkout page"
        }
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml; charset=utf-8"
    assert "<Response><Message>" in response.text
    assert "Issue #42" in response.text

    # Verify DB persistence
    with Session(test_engine) as session:
        mapping = session.exec(select(TicketMapping)).first()
        assert mapping is not None
        assert mapping.whatsapp_number == "whatsapp:+1234567890"
        assert mapping.github_issue_id == 42
        assert mapping.repo_name == "frontend-app"
        assert mapping.issue_title == "Button is not clickable on checkout page"

@patch("main.get_twilio_client")
def test_github_webhook_assigned(mock_get_twilio):
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

    mock_twilio = MagicMock()
    mock_get_twilio.return_value = mock_twilio

    payload = {
        "action": "assigned",
        "issue": {"number": 101},
        "repository": {"name": "backend-api"},
        "assignee": {"login": "alice_dev"}
    }

    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "processed", "action": "assigned"}

    # Verify Twilio notification was triggered
    mock_twilio.messages.create.assert_called_once()
    call_kwargs = mock_twilio.messages.create.call_args.kwargs
    assert call_kwargs["to"] == "whatsapp:+1234567890"
    assert "alice_dev" in call_kwargs["body"]
    assert "Issue #101" in call_kwargs["body"]

@patch("main.get_twilio_client")
def test_github_webhook_closed(mock_get_twilio):
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

    mock_twilio = MagicMock()
    mock_get_twilio.return_value = mock_twilio

    payload = {
        "action": "closed",
        "issue": {"number": 202},
        "repository": {"name": "mobile-app"}
    }

    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "processed", "action": "closed"}

    mock_twilio.messages.create.assert_called_once()
    call_kwargs = mock_twilio.messages.create.call_args.kwargs
    assert call_kwargs["to"] == "whatsapp:+1234567890"
    assert "completed and resolved" in call_kwargs["body"]

def test_github_webhook_untracked():
    payload = {
        "action": "assigned",
        "issue": {"number": 999},
        "repository": {"name": "frontend-app"}
    }
    response = client.post("/webhook/github", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "issue not tracked"}
