"""Tests for PR fetcher — parse_pr_ref and fetch_pr."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prcat.fetcher import PRComment, PRData, fetch_pr, parse_pr_ref


class TestParsePrRef:
    def test_plain_number_with_repo(self):
        repo, number = parse_pr_ref("42", repo="owner/myrepo")
        assert repo == "owner/myrepo"
        assert number == 42

    def test_plain_number_detects_git_remote(self):
        with patch("prcat.fetcher._detect_repo", return_value="org/proj"):
            repo, number = parse_pr_ref("99")
        assert repo == "org/proj"
        assert number == 99

    def test_plain_number_no_repo_raises(self):
        with patch("prcat.fetcher._detect_repo", return_value=None):
            with pytest.raises(ValueError, match="Cannot detect repository"):
                parse_pr_ref("5")

    def test_explicit_repo_hash_format(self):
        repo, number = parse_pr_ref("owner/repo#123")
        assert repo == "owner/repo"
        assert number == 123

    def test_full_url(self):
        url = "https://github.com/cli/cli/pull/456"
        repo, number = parse_pr_ref(url)
        assert repo == "cli/cli"
        assert number == 456

    def test_full_url_with_trailing_params(self):
        url = "https://github.com/cli/cli/pull/456?diff=unified"
        # current regex doesn't strip query params from path, but url_match stops at /456
        repo, number = parse_pr_ref(url)
        assert repo == "cli/cli"
        assert number == 456

    def test_invalid_ref_raises(self):
        with pytest.raises(ValueError, match="Cannot parse PR reference"):
            parse_pr_ref("not-a-pr-ref")


class TestFetchPr:
    def _make_pr_response(self) -> dict:
        return {
            "number": 7,
            "title": "Fix login bug",
            "user": {"login": "alice"},
            "base": {"ref": "main"},
            "head": {"ref": "fix/login"},
            "body": "Fixes #6 — null check was missing",
            "state": "open",
            "additions": 12,
            "deletions": 3,
            "html_url": "https://github.com/org/proj/pull/7",
        }

    def _make_mock_client(self, pr_resp, diff_text, files, comments, issue_comments):
        mock_resp_pr = MagicMock()
        mock_resp_pr.status_code = 200
        mock_resp_pr.json.return_value = pr_resp

        mock_resp_diff = MagicMock()
        mock_resp_diff.status_code = 200
        mock_resp_diff.text = diff_text

        mock_resp_files = MagicMock()
        mock_resp_files.status_code = 200
        mock_resp_files.json.return_value = files

        mock_resp_comments = MagicMock()
        mock_resp_comments.status_code = 200
        mock_resp_comments.json.return_value = comments

        mock_resp_issue_comments = MagicMock()
        mock_resp_issue_comments.status_code = 200
        mock_resp_issue_comments.json.return_value = issue_comments

        mock_client = MagicMock()
        mock_client.get.side_effect = [
            mock_resp_pr,
            mock_resp_diff,
            mock_resp_files,
            mock_resp_comments,
            mock_resp_issue_comments,
        ]
        return mock_client

    def test_fetch_pr_basic(self):
        pr_data = self._make_pr_response()
        files = [{"filename": "src/auth.py"}, {"filename": "src/login.py"}]
        review_comment = [{"user": {"login": "bob"}, "body": "Nice fix", "path": "src/auth.py", "line": 10, "original_line": 10}]
        issue_comment = [{"user": {"login": "charlie"}, "body": "LGTM"}]

        mock_client = self._make_mock_client(
            pr_data, "diff --git a/src/auth.py ...", files, review_comment, issue_comment
        )

        with patch("prcat.fetcher._github_token", return_value="token123"), \
             patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = fetch_pr("org/proj#7")

        assert result.number == 7
        assert result.title == "Fix login bug"
        assert result.author == "alice"
        assert result.base_branch == "main"
        assert result.head_branch == "fix/login"
        assert result.additions == 12
        assert result.deletions == 3
        assert result.repo == "org/proj"
        assert len(result.files_changed) == 2
        assert "src/auth.py" in result.files_changed
        assert len(result.comments) == 2

    def test_fetch_pr_no_comments(self):
        pr_data = self._make_pr_response()
        files = [{"filename": "src/auth.py"}]

        mock_resp_pr = MagicMock()
        mock_resp_pr.status_code = 200
        mock_resp_pr.json.return_value = pr_data

        mock_resp_diff = MagicMock()
        mock_resp_diff.status_code = 200
        mock_resp_diff.text = "diff text"

        mock_resp_files = MagicMock()
        mock_resp_files.status_code = 200
        mock_resp_files.json.return_value = files

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_resp_pr, mock_resp_diff, mock_resp_files]

        with patch("prcat.fetcher._github_token", return_value=None), \
             patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = fetch_pr("org/proj#7", include_comments=False)

        assert result.comments == []

    def test_fetch_pr_404_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("prcat.fetcher._github_token", return_value=None), \
             patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(ValueError, match="not found"):
                fetch_pr("org/proj#999")

    def test_fetch_pr_401_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("prcat.fetcher._github_token", return_value=None), \
             patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(ValueError, match="authentication failed"):
                fetch_pr("org/proj#1")
