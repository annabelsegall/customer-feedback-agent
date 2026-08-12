from typing import Optional, List
from github import Github, GithubException
from config import GITHUB_TOKEN, GITHUB_ORG_OR_USER

def get_github_client() -> Optional[Github]:
    if GITHUB_TOKEN:
        return Github(GITHUB_TOKEN)
    return None

def get_or_create_label(repo, label_name: str, color: str = "0075ca"):
    try:
        return repo.get_label(label_name)
    except GithubException:
        try:
            return repo.create_label(name=label_name, color=color)
        except Exception as e:
            print(f"Warning: Could not create label '{label_name}': {e}")
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
        
        # 1. Ensure 'whatsapp' label exists and add it
        wa_label = get_or_create_label(repo, "whatsapp", color="25D366")
        if wa_label:
            labels_to_apply.append(wa_label)

        # 2. Ensure Priority label exists and add it
        if priority:
            p_name = priority.capitalize()
            color_map = {"High": "d93f0b", "Medium": "fbca04", "Low": "0e8a16"}
            p_color = color_map.get(p_name, "0075ca")
            p_label = get_or_create_label(repo, p_name, color=p_color)
            if p_label:
                labels_to_apply.append(p_label)

        # Create issue with guaranteed labels
        if labels_to_apply:
            issue = repo.create_issue(title=title, body=issue_body, labels=labels_to_apply)
        else:
            issue = repo.create_issue(title=title, body=issue_body)

        return issue.number
    except Exception as e:
        print(f"Error creating GitHub issue: {e}")
        return 1
