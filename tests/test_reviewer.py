"""Tests for AI reviewer logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prcat.fetcher import PRData
from prcat.reviewer import (
    ReviewResult,
    _build_prompt,
    _extract_verdict,
    _truncate_diff,
    review_pr,
)


def _make_pr(diff: str = "diff text", body: str = "Fixes a bug", comments=None) -> PRData:
    return PRData(
        number=42,
        title="Add feature X",
        author="alice",
        base_branch="main",
        head_branch="feature/x",
        body=body,
        state="open",
        diff=diff,
        files_changed=["src/foo.py"],
        additions=10,
        deletions=2,
        comments=comments or [],
        repo="org/proj",
        url="https://github.com/org/proj/pull/42",
    )


class TestTruncateDiff:
    def test_no_truncation_needed(self):
        diff = "x" * 1000
        result, truncated = _truncate_diff(diff, max_chars=2000)
        assert result == diff
        assert truncated is False

    def test_truncation_happens(self):
        diff = "x" * 5000
        result, truncated = _truncate_diff(diff, max_chars=3000)
        assert len(result) <= 3100  # some slack for truncation message
        assert truncated is True
        assert "truncated" in result


class TestExtractVerdict:
    def test_lgtm(self):
        verdict, critical, warnings = _extract_verdict("LGTM, no issues found")
        assert verdict == "lgtm"
        assert not critical
        assert not warnings

    def test_critical(self):
        verdict, critical, warnings = _extract_verdict("Found [CRITICAL] SQL injection")
        assert verdict == "needs-major-changes"
        assert critical

    def test_warning(self):
        verdict, critical, warnings = _extract_verdict("There is a [WARNING] about null pointer")
        assert verdict == "needs-minor-changes"
        assert warnings

    def test_major_changes_text(self):
        verdict, critical, warnings = _extract_verdict("Needs major changes before merging.")
        assert verdict == "needs-major-changes"

    def test_minor_changes_text(self):
        verdict, critical, warnings = _extract_verdict("Needs minor changes ⚠️")
        assert verdict == "needs-minor-changes"

    def test_default_reviewed(self):
        verdict, critical, warnings = _extract_verdict("Some text without clear verdict.")
        assert verdict == "reviewed"


class TestBuildPrompt:
    def test_review_style(self):
        pr = _make_pr()
        prompt = _build_prompt(pr, "review", "diff text")
        assert "PR #42" in prompt
        assert "Add feature X" in prompt
        assert "Verdict" in prompt
        assert "Concerns" in prompt

    def test_summary_style(self):
        pr = _make_pr()
        prompt = _build_prompt(pr, "summary", "diff text")
        assert "What it does" in prompt
        assert "Key changes" in prompt

    def test_risks_style(self):
        pr = _make_pr()
        prompt = _build_prompt(pr, "risks", "diff text")
        assert "Security risks" in prompt
        assert "Breaking changes" in prompt

    def test_comments_included(self):
        from prcat.fetcher import PRComment
        pr = _make_pr(comments=[
            PRComment(author="bob", body="This looks suspicious", path="src/foo.py", line=10)
        ])
        prompt = _build_prompt(pr, "review", "diff text")
        assert "bob" in prompt
        assert "This looks suspicious" in prompt

    def test_no_body_handled(self):
        pr = _make_pr(body="")
        prompt = _build_prompt(pr, "review", "diff text")
        assert "no description" in prompt


class TestReviewPr:
    def test_review_claude(self):
        pr = _make_pr()
        mock_response = "## Summary\nThis adds feature X.\n\n**Verdict**: LGTM ✅\n\nNo concerns."

        with patch("prcat.reviewer._call_claude", return_value=mock_response):
            result = review_pr(pr, provider="claude")

        assert result.pr_number == 42
        assert result.verdict == "lgtm"
        assert not result.has_critical
        assert result.raw_text == mock_response

    def test_review_with_critical(self):
        pr = _make_pr()
        mock_response = "[CRITICAL] SQL injection found in src/foo.py line 42. Use parameterized queries."

        with patch("prcat.reviewer._call_claude", return_value=mock_response):
            result = review_pr(pr, provider="claude")

        assert result.has_critical
        assert result.verdict == "needs-major-changes"

    def test_review_openai(self):
        pr = _make_pr()
        mock_response = "Looks good with [WARNING] minor issue."

        with patch("prcat.reviewer._call_openai", return_value=mock_response):
            result = review_pr(pr, provider="openai")

        assert result.has_warnings
        assert not result.has_critical

    def test_review_ollama(self):
        pr = _make_pr()
        mock_response = "Needs minor changes ⚠️"

        with patch("prcat.reviewer._call_ollama", return_value=mock_response):
            result = review_pr(pr, provider="ollama")

        assert result.verdict == "needs-minor-changes"

    def test_unknown_provider_raises(self):
        pr = _make_pr()
        with pytest.raises(ValueError, match="Unknown provider"):
            review_pr(pr, provider="gpt5-turbo")

    def test_large_diff_is_truncated(self):
        large_diff = "+" * 50_000
        pr = _make_pr(diff=large_diff)

        with patch("prcat.reviewer._call_claude", return_value="LGTM") as mock_call:
            result = review_pr(pr, provider="claude")
            prompt_sent = mock_call.call_args[0][0]
            assert "truncated" in prompt_sent

        assert result.diff_truncated
