"""Tests for app.services.repo_service — GitHub URL handling & cloning."""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.services.repo_service import (
    RepoInfo,
    RepoService,
    RepoServiceConfig,
    is_github_url,
    parse_github_url,
)

# ── is_github_url ────────────────────────────────────────────────────────────


class TestIsGithubUrl:
    def test_https(self):
        assert is_github_url("https://github.com/owner/repo") is True

    def test_http(self):
        assert is_github_url("http://github.com/owner/repo") is True

    def test_ssh(self):
        assert is_github_url("git@github.com:owner/repo") is True

    def test_local_path(self):
        assert is_github_url("/home/user/project") is False

    def test_other_url(self):
        assert is_github_url("https://gitlab.com/owner/repo") is False

    def test_empty_string(self):
        assert is_github_url("") is False

    def test_windows_path(self):
        assert is_github_url("C:\\Users\\test\\project") is False


# ── parse_github_url ─────────────────────────────────────────────────────────


class TestParseGithubUrl:
    def test_basic_https(self):
        info = parse_github_url("https://github.com/owner/repo")
        assert info.owner == "owner"
        assert info.name == "repo"

    def test_git_suffix(self):
        info = parse_github_url("https://github.com/owner/repo.git")
        assert info.name == "repo"

    def test_trailing_slash(self):
        info = parse_github_url("https://github.com/owner/repo/")
        assert info.name == "repo"

    def test_ssh(self):
        info = parse_github_url("git@github.com:owner/repo")
        assert info.owner == "owner"
        assert info.name == "repo"

    def test_branch_url(self):
        info = parse_github_url("https://github.com/owner/repo/tree/develop")
        assert info.owner == "owner"
        assert info.name == "repo"
        assert info.branch == "develop"

    def test_whitespace(self):
        info = parse_github_url("  https://github.com/owner/repo  ")
        assert info.owner == "owner"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("not-a-url")

    def test_non_github_raises(self):
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("https://gitlab.com/owner/repo")


# ── RepoService.resolve_path ────────────────────────────────────────────────


class TestRepoServiceResolveLocal:
    @pytest.mark.asyncio
    async def test_resolve_local_dir(self, tmp_path):
        svc = RepoService(RepoServiceConfig(storage_path=str(tmp_path / "store")))
        result = await svc.resolve_path(str(tmp_path))
        assert os.path.isabs(result)
        assert os.path.isdir(result)

    @pytest.mark.asyncio
    async def test_nonexistent_raises(self, tmp_path):
        svc = RepoService(RepoServiceConfig(storage_path=str(tmp_path / "store")))
        with pytest.raises(ValueError, match="not found"):
            await svc.resolve_path(str(tmp_path / "nope"))

    @pytest.mark.asyncio
    async def test_github_url_delegates_to_clone(self, tmp_path):
        svc = RepoService(RepoServiceConfig(storage_path=str(tmp_path / "store")))
        fake_info = RepoInfo(
            owner="owner",
            name="repo",
            url="https://github.com/owner/repo",
            local_path=str(tmp_path),
        )
        with patch.object(svc, "clone", new_callable=AsyncMock, return_value=fake_info):
            result = await svc.resolve_path("https://github.com/owner/repo")
            assert result == str(tmp_path)


# ── cache validity ───────────────────────────────────────────────────────────


class TestCacheValidity:
    def test_valid_cache(self, tmp_path):
        svc = RepoService(
            RepoServiceConfig(
                storage_path=str(tmp_path / "store"),
                cache_ttl_hours=24,
            )
        )
        info = RepoInfo(
            owner="o",
            name="n",
            url="https://github.com/o/n",
            cloned_at=datetime.now(),
        )
        assert svc._is_cache_valid(info) is True

    def test_expired_cache(self, tmp_path):
        svc = RepoService(
            RepoServiceConfig(
                storage_path=str(tmp_path / "store"),
                cache_ttl_hours=1,
            )
        )
        info = RepoInfo(
            owner="o",
            name="n",
            url="https://github.com/o/n",
            cloned_at=datetime.now() - timedelta(hours=2),
        )
        assert svc._is_cache_valid(info) is False

    def test_no_timestamp(self, tmp_path):
        svc = RepoService(RepoServiceConfig(storage_path=str(tmp_path / "store")))
        info = RepoInfo(owner="o", name="n", url="https://github.com/o/n")
        assert svc._is_cache_valid(info) is False


# ── _get_local_path ──────────────────────────────────────────────────────────


class TestGetLocalPath:
    def test_includes_owner_and_name(self, tmp_path):
        svc = RepoService(RepoServiceConfig(storage_path=str(tmp_path / "store")))
        info = RepoInfo(
            owner="alice",
            name="myrepo",
            url="https://github.com/alice/myrepo",
        )
        local = svc._get_local_path(info)
        assert "alice" in str(local)
        assert "myrepo" in str(local)

    def test_under_storage_path(self, tmp_path):
        store = tmp_path / "store"
        svc = RepoService(RepoServiceConfig(storage_path=str(store)))
        info = RepoInfo(owner="a", name="b", url="https://github.com/a/b")
        local = svc._get_local_path(info)
        assert str(local).startswith(str(store))
