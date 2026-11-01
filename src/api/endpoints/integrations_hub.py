"""Integrations hub — Slack, Jira, GitHub, Teams."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _get(request: Request, key: str, label: str):
    obj = getattr(request.app.state, key, None)
    if obj is None:
        raise HTTPException(status_code=503, detail=f"{label} not configured")
    return obj


# ── Slack ─────────────────────────────────────────────────────────────────────

class SlackMessageRequest(BaseModel):
    channel: str
    text: str
    blocks: Optional[List[Dict[str, Any]]] = None


class SlackWebhookRequest(BaseModel):
    text: str
    blocks: Optional[List[Dict[str, Any]]] = None


@router.post("/slack/message", summary="Post a message to Slack")
async def slack_post_message(body: SlackMessageRequest, request: Request) -> Dict[str, Any]:
    slack = _get(request, "slack_integration", "Slack")
    return await slack.post_message(channel=body.channel, text=body.text, blocks=body.blocks)


@router.post("/slack/webhook", summary="Send via Slack Incoming Webhook")
async def slack_webhook(body: SlackWebhookRequest, request: Request) -> Dict[str, Any]:
    slack = _get(request, "slack_integration", "Slack")
    ok = await slack.send_webhook(text=body.text, blocks=body.blocks)
    return {"ok": ok}


@router.get("/slack/channels", summary="List Slack channels")
async def slack_channels(request: Request) -> Dict[str, Any]:
    slack = _get(request, "slack_integration", "Slack")
    channels = await slack.list_channels()
    return {"channels": channels, "total": len(channels)}


# ── Jira ──────────────────────────────────────────────────────────────────────

class JiraIssueCreateRequest(BaseModel):
    project_key: str
    summary: str
    issue_type: str = "Task"
    description: Optional[str] = None
    priority: str = "Medium"


class JiraCommentRequest(BaseModel):
    text: str


@router.get("/jira/projects", summary="List Jira projects")
async def jira_projects(request: Request) -> Dict[str, Any]:
    jira = _get(request, "jira_integration", "Jira")
    projects = await jira.list_projects()
    return {"projects": projects}


@router.get("/jira/issues", summary="Search Jira issues via JQL")
async def jira_search(
    jql: str = "order by created DESC",
    max_results: int = 50,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    jira = _get(request, "jira_integration", "Jira")
    return await jira.search_issues(jql=jql, max_results=max_results)


@router.get("/jira/issues/{issue_key}", summary="Get a Jira issue")
async def jira_get_issue(issue_key: str, request: Request) -> Dict[str, Any]:
    jira = _get(request, "jira_integration", "Jira")
    return await jira.get_issue(issue_key)


@router.post("/jira/issues", summary="Create a Jira issue")
async def jira_create_issue(body: JiraIssueCreateRequest, request: Request) -> Dict[str, Any]:
    jira = _get(request, "jira_integration", "Jira")
    return await jira.create_issue(
        project_key=body.project_key,
        summary=body.summary,
        issue_type=body.issue_type,
        description=body.description,
        priority=body.priority,
    )


@router.post("/jira/issues/{issue_key}/comments", summary="Add comment to Jira issue")
async def jira_add_comment(issue_key: str, body: JiraCommentRequest, request: Request) -> Dict[str, Any]:
    jira = _get(request, "jira_integration", "Jira")
    return await jira.add_comment(issue_key=issue_key, text=body.text)


# ── GitHub ────────────────────────────────────────────────────────────────────

class GitHubIssueRequest(BaseModel):
    title: str
    body: str = ""
    labels: Optional[List[str]] = None


class GitHubCommentRequest(BaseModel):
    body: str


@router.get("/github/{owner}/{repo}/issues", summary="List GitHub issues")
async def github_list_issues(
    owner: str, repo: str, state: str = "open",
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    gh = _get(request, "github_integration", "GitHub")
    issues = await gh.list_issues(owner=owner, repo=repo, state=state)
    return {"issues": issues, "total": len(issues)}


@router.post("/github/{owner}/{repo}/issues", summary="Create a GitHub issue")
async def github_create_issue(
    owner: str, repo: str, body: GitHubIssueRequest, request: Request
) -> Dict[str, Any]:
    gh = _get(request, "github_integration", "GitHub")
    return await gh.create_issue(owner=owner, repo=repo, title=body.title, body=body.body, labels=body.labels)


@router.get("/github/{owner}/{repo}/pulls", summary="List GitHub pull requests")
async def github_list_prs(
    owner: str, repo: str, state: str = "open",
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    gh = _get(request, "github_integration", "GitHub")
    prs = await gh.list_pull_requests(owner=owner, repo=repo, state=state)
    return {"pull_requests": prs, "total": len(prs)}


@router.get("/github/{owner}/{repo}/runs", summary="List GitHub Actions workflow runs")
async def github_workflow_runs(
    owner: str, repo: str,
    request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    gh = _get(request, "github_integration", "GitHub")
    return await gh.get_workflow_runs(owner=owner, repo=repo)


# ── Teams ─────────────────────────────────────────────────────────────────────

class TeamsMessageRequest(BaseModel):
    text: str
    title: Optional[str] = None


@router.post("/teams/message", summary="Send a Teams message")
async def teams_message(body: TeamsMessageRequest, request: Request) -> Dict[str, Any]:
    teams = _get(request, "teams_integration", "Teams")
    ok = await teams.send_message(text=body.text, title=body.title)
    return {"ok": ok}


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status", summary="Integration connectivity status")
async def integrations_status(request: Request) -> Dict[str, Any]:
    return {
        "slack": getattr(request.app.state, "slack_integration", None) is not None,
        "jira": getattr(request.app.state, "jira_integration", None) is not None,
        "github": getattr(request.app.state, "github_integration", None) is not None,
        "teams": getattr(request.app.state, "teams_integration", None) is not None,
    }
