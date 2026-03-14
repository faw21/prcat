"""AI review engine — sends PR data to LLM and parses the response."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .fetcher import PRData


_MAX_DIFF_CHARS = 40_000  # ~10k tokens of diff


def _truncate_diff(diff: str, max_chars: int = _MAX_DIFF_CHARS) -> tuple[str, bool]:
    """Truncate diff to stay within token budget."""
    if len(diff) <= max_chars:
        return diff, False
    return diff[:max_chars] + "\n\n[diff truncated — showing first portion only]", True


def _build_prompt(pr: PRData, style: str, diff: str) -> str:
    """Build the review prompt."""
    comments_section = ""
    if pr.comments:
        lines = ["\n## Existing Review Comments\n"]
        for c in pr.comments[:20]:  # cap at 20 comments
            loc = f" ({c.path}:{c.line})" if c.path else ""
            lines.append(f"**{c.author}**{loc}: {c.body[:500]}")
        comments_section = "\n".join(lines)

    if style == "summary":
        task = (
            "Provide a concise summary of this pull request:\n"
            "1. **What it does** (2-3 sentences)\n"
            "2. **Key changes** (bullet list of main modifications)\n"
            "3. **Impact** (what breaks/improves, scope of change)\n"
        )
    elif style == "risks":
        task = (
            "Focus ONLY on risks and concerns in this pull request:\n"
            "1. **Security risks** (auth, injection, exposure)\n"
            "2. **Correctness issues** (logic errors, edge cases, race conditions)\n"
            "3. **Breaking changes** (API changes, data migrations, compatibility)\n"
            "4. **Performance concerns** (N+1, memory, blocking calls)\n"
            "If no significant risks, say so explicitly.\n"
        )
    else:  # review (default)
        task = (
            "Provide a structured code review of this pull request:\n"
            "1. **Summary** — what this PR does in 2-3 sentences\n"
            "2. **Verdict** — one of: LGTM ✅ | Needs minor changes ⚠️ | Needs major changes 🚨\n"
            "3. **Concerns** — list issues with severity [CRITICAL], [WARNING], or [INFO]. "
            "Be specific: file, line, issue, suggested fix.\n"
            "4. **Questions for author** — list clarifying questions if any\n"
            "5. **Suggested review comment** — a polished comment you could paste into GitHub\n"
        )

    return f"""You are an expert code reviewer. Review this pull request.

## PR #{pr.number}: {pr.title}
**Author:** {pr.author}
**Branch:** {pr.head_branch} → {pr.base_branch}
**Changes:** +{pr.additions}/-{pr.deletions} lines across {len(pr.files_changed)} files
**Files:** {', '.join(pr.files_changed[:20])}{'...' if len(pr.files_changed) > 20 else ''}

## PR Description
{pr.body or '(no description provided)'}
{comments_section}

## Diff
```diff
{diff}
```

---
{task}
Keep the review practical and actionable. Focus on real issues, not style nitpicks unless they matter.
"""


@dataclass
class ReviewResult:
    pr_number: int
    pr_title: str
    pr_url: str
    raw_text: str
    verdict: str = "reviewed"
    has_critical: bool = False
    has_warnings: bool = False
    diff_truncated: bool = False


def _extract_verdict(text: str) -> tuple[str, bool, bool]:
    """Extract verdict and severity flags from review text."""
    has_critical = bool(re.search(r"\[CRITICAL\]", text, re.IGNORECASE))
    has_warnings = bool(re.search(r"\[WARNING\]", text, re.IGNORECASE))

    # Look for explicit verdict line
    lgtm_match = re.search(r"LGTM|looks good to me|no issues", text, re.IGNORECASE)
    major_match = re.search(r"needs major changes|major changes|🚨", text)
    minor_match = re.search(r"needs minor changes|minor changes|⚠️", text)

    if has_critical or major_match:
        verdict = "needs-major-changes"
    elif has_warnings or minor_match:
        verdict = "needs-minor-changes"
    elif lgtm_match:
        verdict = "lgtm"
    else:
        verdict = "reviewed"

    return verdict, has_critical, has_warnings


def _call_claude(prompt: str, model: Optional[str]) -> str:
    import anthropic
    client = anthropic.Anthropic()
    model = model or "claude-haiku-4-5"
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _call_openai(prompt: str, model: Optional[str]) -> str:
    from openai import OpenAI
    client = OpenAI()
    model = model or "gpt-4o-mini"
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _call_ollama(prompt: str, model: Optional[str]) -> str:
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    model = model or "qwen2.5:1.5b"
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def review_pr(
    pr: PRData,
    style: str = "review",
    provider: str = "claude",
    model: Optional[str] = None,
) -> ReviewResult:
    """Run AI review on a PR and return structured result."""
    diff, truncated = _truncate_diff(pr.diff)
    prompt = _build_prompt(pr, style, diff)

    if provider == "claude":
        raw = _call_claude(prompt, model)
    elif provider == "openai":
        raw = _call_openai(prompt, model)
    elif provider == "ollama":
        raw = _call_ollama(prompt, model)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Use: claude, openai, ollama")

    verdict, has_critical, has_warnings = _extract_verdict(raw)

    return ReviewResult(
        pr_number=pr.number,
        pr_title=pr.title,
        pr_url=pr.url,
        raw_text=raw,
        verdict=verdict,
        has_critical=has_critical,
        has_warnings=has_warnings,
        diff_truncated=truncated,
    )
