"""Tests for helper functions: _github_token and _detect_repo."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from prcat.fetcher import _detect_repo, _github_token


class TestGithubToken:
    def test_returns_github_token_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "my-token")
        assert _github_token() == "my-token"

    def test_returns_gh_token_env(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh-tok")
        assert _github_token() == "gh-tok"

    def test_falls_back_to_gh_cli(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "cli-token\n"
        with patch("subprocess.run", return_value=mock_result):
            token = _github_token()
        assert token == "cli-token"

    def test_gh_cli_failure_returns_none(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            token = _github_token()
        assert token is None

    def test_gh_cli_not_found_returns_none(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            token = _github_token()
        assert token is None

    def test_gh_cli_timeout_returns_none(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["gh"], 5)):
            token = _github_token()
        assert token is None


class TestDetectRepo:
    def test_detects_https_remote(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/owner/myrepo.git\n"
        with patch("subprocess.run", return_value=mock_result):
            repo = _detect_repo()
        assert repo == "owner/myrepo"

    def test_detects_ssh_remote(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git@github.com:owner/myrepo.git\n"
        with patch("subprocess.run", return_value=mock_result):
            repo = _detect_repo()
        assert repo == "owner/myrepo"

    def test_non_github_remote_returns_none(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://gitlab.com/owner/repo.git\n"
        with patch("subprocess.run", return_value=mock_result):
            repo = _detect_repo()
        assert repo is None

    def test_git_command_fails_returns_none(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            repo = _detect_repo()
        assert repo is None

    def test_git_not_installed_returns_none(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            repo = _detect_repo()
        assert repo is None

    def test_git_timeout_returns_none(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 5)):
            repo = _detect_repo()
        assert repo is None
