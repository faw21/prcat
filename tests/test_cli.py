"""Tests for CLI interface."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from prcat.cli import main
from prcat.fetcher import PRData
from prcat.reviewer import ReviewResult


def _make_pr() -> PRData:
    return PRData(
        number=5,
        title="Refactor login",
        author="dev1",
        base_branch="main",
        head_branch="refactor/login",
        body="Cleans up auth code",
        state="open",
        diff="diff text",
        files_changed=["auth.py"],
        additions=20,
        deletions=10,
        comments=[],
        repo="org/repo",
        url="https://github.com/org/repo/pull/5",
    )


def _make_result(verdict="lgtm", has_critical=False, has_warnings=False) -> ReviewResult:
    return ReviewResult(
        pr_number=5,
        pr_title="Refactor login",
        pr_url="https://github.com/org/repo/pull/5",
        raw_text="LGTM — looks good to me.",
        verdict=verdict,
        has_critical=has_critical,
        has_warnings=has_warnings,
        diff_truncated=False,
    )


class TestCliMain:
    def test_basic_review(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj):
            result = runner.invoke(main, ["org/repo#5"])

        assert result.exit_code == 0
        assert "Refactor login" in result.output

    def test_critical_exits_1(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result(verdict="needs-major-changes", has_critical=True)

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj):
            result = runner.invoke(main, ["org/repo#5"])

        assert result.exit_code == 1

    def test_compact_mode(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj):
            result = runner.invoke(main, ["org/repo#5", "--compact"])

        assert result.exit_code == 0
        assert "LGTM" in result.output.upper()

    def test_value_error_exits_2(self):
        runner = CliRunner()

        with patch("prcat.cli.fetch_pr", side_effect=ValueError("PR not found")):
            result = runner.invoke(main, ["org/repo#999"])

        assert result.exit_code == 2
        assert "Error" in result.output

    def test_summary_style(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr) as mock_fetch, \
             patch("prcat.cli.review_pr", return_value=result_obj) as mock_review:
            result = runner.invoke(main, ["org/repo#5", "--style", "summary"])

        assert result.exit_code == 0
        call_kwargs = mock_review.call_args
        assert call_kwargs[1]["style"] == "summary" or call_kwargs[0][1] == "summary"

    def test_risks_style(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj) as mock_review:
            result = runner.invoke(main, ["org/repo#5", "--style", "risks"])

        assert result.exit_code == 0
        args, kwargs = mock_review.call_args
        assert kwargs.get("style", args[1] if len(args) > 1 else None) == "risks"

    def test_provider_option(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj) as mock_review:
            result = runner.invoke(main, ["org/repo#5", "--provider", "openai"])

        assert result.exit_code == 0
        args, kwargs = mock_review.call_args
        assert kwargs.get("provider", args[2] if len(args) > 2 else None) == "openai"

    def test_output_file(self, tmp_path):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()
        outfile = tmp_path / "review.md"

        with patch("prcat.cli.fetch_pr", return_value=pr), \
             patch("prcat.cli.review_pr", return_value=result_obj):
            result = runner.invoke(main, ["org/repo#5", "--output", str(outfile)])

        assert result.exit_code == 0
        assert outfile.exists()
        content = outfile.read_text()
        assert "PR #5" in content

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "prcat" in result.output

    def test_no_comments_flag(self):
        runner = CliRunner()
        pr = _make_pr()
        result_obj = _make_result()

        with patch("prcat.cli.fetch_pr", return_value=pr) as mock_fetch, \
             patch("prcat.cli.review_pr", return_value=result_obj):
            result = runner.invoke(main, ["org/repo#5", "--no-comments"])

        assert result.exit_code == 0
        _, kwargs = mock_fetch.call_args
        assert kwargs.get("include_comments") is False
