"""GitHub PR fetcher — pulls PR data via GitHub API."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class PRComment:
    author: str
    body: str
    path: Optional[str] = None
    line: Optional[int] = None


@dataclass
class PRData:
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    body: str
    state: str
    diff: str
    files_changed: list[str]
    additions: int
    deletions: int
    comments: list[PRComment] = field(default_factory=list)
    repo: str = ""
    url: str = ""


def _github_token() -> Optional[str]:
    """Get GitHub token from env or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _detect_repo() -> Optional[str]:
    """Detect owner/repo from current git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
        # https://github.com/owner/repo.git or git@github.com:owner/repo.git
        match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def parse_pr_ref(pr_ref: str, repo: Optional[str] = None) -> tuple[str, int]:
    """Parse PR reference into (owner/repo, number).

    Accepts:
      - "123"                                  → uses detected/provided repo
      - "owner/repo#123"                       → explicit repo
      - "https://github.com/owner/repo/pull/123"
    """
    # URL form
    url_match = re.match(
        r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_ref
    )
    if url_match:
        return url_match.group(1), int(url_match.group(2))

    # owner/repo#number form
    ref_match = re.match(r"([^/]+/[^/#]+)#(\d+)", pr_ref)
    if ref_match:
        return ref_match.group(1), int(ref_match.group(2))

    # plain number — needs repo from context
    if pr_ref.isdigit():
        detected = repo or _detect_repo()
        if not detected:
            raise ValueError(
                "Cannot detect repository. Use a full URL or owner/repo#number format, "
                "or run from inside a git repository with a GitHub remote."
            )
        return detected, int(pr_ref)

    raise ValueError(
        f"Cannot parse PR reference '{pr_ref}'. "
        "Use a number, owner/repo#number, or full GitHub URL."
    )


def fetch_pr(pr_ref: str, repo: Optional[str] = None, include_comments: bool = True) -> PRData:
    """Fetch PR data from GitHub API."""
    owner_repo, number = parse_pr_ref(pr_ref, repo)
    token = _github_token()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    base_url = f"https://api.github.com/repos/{owner_repo}"

    with httpx.Client(timeout=30) as client:
        # Fetch PR metadata
        resp = client.get(f"{base_url}/pulls/{number}", headers=headers)
        if resp.status_code == 404:
            raise ValueError(f"PR #{number} not found in {owner_repo}.")
        if resp.status_code == 401:
            raise ValueError("GitHub authentication failed. Set GITHUB_TOKEN or log in with 'gh auth login'.")
        resp.raise_for_status()
        pr = resp.json()

        # Fetch diff
        diff_headers = {**headers, "Accept": "application/vnd.github.v3.diff"}
        diff_resp = client.get(f"{base_url}/pulls/{number}", headers=diff_headers)
        diff_resp.raise_for_status()
        diff = diff_resp.text

        # Fetch files changed
        files_resp = client.get(f"{base_url}/pulls/{number}/files", headers=headers)
        files_resp.raise_for_status()
        files = [f["filename"] for f in files_resp.json()]

        # Optionally fetch comments
        comments: list[PRComment] = []
        if include_comments:
            # PR review comments (inline)
            review_comments_resp = client.get(
                f"{base_url}/pulls/{number}/comments", headers=headers
            )
            review_comments_resp.raise_for_status()
            for c in review_comments_resp.json():
                comments.append(PRComment(
                    author=c["user"]["login"],
                    body=c["body"],
                    path=c.get("path"),
                    line=c.get("line") or c.get("original_line"),
                ))

            # Issue comments (general PR comments)
            issue_comments_resp = client.get(
                f"{base_url}/issues/{number}/comments", headers=headers
            )
            issue_comments_resp.raise_for_status()
            for c in issue_comments_resp.json():
                comments.append(PRComment(
                    author=c["user"]["login"],
                    body=c["body"],
                ))

    return PRData(
        number=number,
        title=pr["title"],
        author=pr["user"]["login"],
        base_branch=pr["base"]["ref"],
        head_branch=pr["head"]["ref"],
        body=pr.get("body") or "",
        state=pr["state"],
        diff=diff,
        files_changed=files,
        additions=pr.get("additions", 0),
        deletions=pr.get("deletions", 0),
        comments=comments,
        repo=owner_repo,
        url=pr["html_url"],
    )
