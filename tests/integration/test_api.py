"""Integration tests for the HTTP API (mcp_server.py)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from mcp_server import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Health endpoint ──────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_status_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_tools_listed(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert len(data["tools"]) == 5
        assert "repo_overview" in data["tools"]
        assert "search_code" in data["tools"]


# ── list_directory endpoint ──────────────────────────────────────────────────


class TestListDirectoryEndpoint:
    def test_valid_directory(self, client, sample_project):
        resp = client.post("/list_directory", json={"path": str(sample_project)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "entries" in data["result"]

    def test_nonexistent_directory(self, client, tmp_path):
        resp = client.post("/list_directory", json={"path": str(tmp_path / "nope")})
        assert resp.status_code == 200
        data = resp.json()
        assert "Empty or not found" in data["result"] or data["success"] is True


# ── read_file endpoint ──────────────────────────────────────────────────────


class TestReadFileEndpoint:
    def test_existing_file(self, client, sample_file):
        resp = client.post("/read_file", json={"path": str(sample_file)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "line 1:" in data["result"]

    def test_nonexistent_file(self, client, tmp_path):
        resp = client.post("/read_file", json={"path": str(tmp_path / "nope.py")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_line_range(self, client, sample_file):
        resp = client.post(
            "/read_file",
            json={"path": str(sample_file), "start_line": 3, "end_line": 7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ── search_code endpoint ────────────────────────────────────────────────────


class TestSearchCodeEndpoint:
    def test_finds_match(self, client, sample_project):
        resp = client.post(
            "/search_code",
            json={"query": "hello", "path": str(sample_project)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "match" in data["result"].lower() or "hello" in data["result"].lower()

    def test_no_matches(self, client, sample_project):
        resp = client.post(
            "/search_code",
            json={"query": "zzz_nomatch_zzz", "path": str(sample_project)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "no match" in data["result"].lower()

    def test_invalid_dir(self, client, tmp_path):
        resp = client.post(
            "/search_code",
            json={"query": "test", "path": str(tmp_path / "nope")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


# ── find_files endpoint ──────────────────────────────────────────────────────


class TestFindFilesEndpoint:
    def test_finds_python_files(self, client, sample_project):
        resp = client.post(
            "/find_files",
            json={"pattern": "**/*.py", "path": str(sample_project)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert ".py" in data["result"]

    def test_no_match(self, client, sample_project):
        resp = client.post(
            "/find_files",
            json={"pattern": "**/*.zzz", "path": str(sample_project)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "no files" in data["result"].lower()


# ── repo_overview endpoint ───────────────────────────────────────────────────


class TestRepoOverviewEndpoint:
    def test_local_path(self, client, sample_project):
        with patch("mcp_server._get_repo_service") as mock_svc:
            mock_instance = mock_svc.return_value
            mock_instance.resolve_path = AsyncMock(return_value=str(sample_project))
            resp = client.post("/repo_overview", json={"path": str(sample_project)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Repository:" in data["result"] or len(data["result"]) > 0
