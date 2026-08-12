from typing import Optional
from github import Github, GithubException
from config import GITHUB_TOKEN, GITHUB_ORG_OR_USER

def get_github_client() -> Optional[Github]:
    if GITHUB_TOKEN:
        return Github(GITHUB_TOKEN)
    return None

def create_github_issue(
    target_repo_name: str,
    title: str,
    description: str,
    priority: str
) -> int:
    if "/" in target_repo_name:
        full_repo_path = target_repo_name
    else:
        full_repo_path = f"{GITHUB_ORG_OR_USER}/{target_repo_name}" if GITHUB_ORG_OR_USER else target_repo_name

    gh_client = get_github_client()
    if not gh_client:
        return 1

    try:
        repo = gh_client.get_repo(full_repo_path)
        issue_body = (
            f"{description}\n\n---\n"
            f"**Submitted via:** WhatsApp\n"
            f"**Priority:** {priority}"
        )
        
        labels_to_apply = []
        if priority:
            labels_to_apply.append(priority.lower())
            try:
                issue = repo.create_issue(title=title, body=issue_body, labels=labels_to_apply)
            except GithubException:
                # Fallback without labels if missing on target repo
                issue = repo.create_issue(title=title, body=issue_body)
        else:
            issue = repo.create_issue(title=title, body=issue_body)

        return issue.number
    except Exception as e:
        print(f"Error creating GitHub issue: {e}")
        return 1
