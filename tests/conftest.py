"""Shared test fixtures for Scout test suite."""

import json
import os

import pytest


@pytest.fixture
def sample_project(tmp_path):
    """Create a realistic multi-language project tree for testing."""
    # Python files
    (tmp_path / "main.py").write_text("print('hello world')\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_utils.py").write_text(
        "from src.utils import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )

    # JS/TS files
    (tmp_path / "app.js").write_text("const express = require('express');\n")
    (tmp_path / "src" / "server.ts").write_text(
        "import express from 'express';\nconst app = express();\n"
    )
    (tmp_path / "src" / "components").mkdir()
    (tmp_path / "src" / "components" / "button.tsx").write_text(
        "export const Button = () => <button>Click</button>;\n"
    )

    # Config files
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "test-project",
                "dependencies": {"react": "^18.0.0", "vite": "^5.0.0"},
            }
        )
    )
    (tmp_path / "requirements.txt").write_text("fastapi>=0.109.0\nuvicorn\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\nCOPY . /app\n")
    (tmp_path / "docker-compose.yml").write_text(
        "version: '3'\nservices:\n  app:\n    build: .\n"
    )
    (tmp_path / "Makefile").write_text("run:\n\tpython main.py\n")
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    (tmp_path / ".env").write_text("SECRET=abc\n")

    # Data / docs
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.yaml").write_text("key: value\n")
    (tmp_path / "data" / "config.json").write_text('{"key": "value"}\n')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\nSome docs.\n")

    # README
    (tmp_path / "README.md").write_text("# Test Project\nA test project.\n")

    # Directories that should be skipped
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "lodash.js").write_text("module.exports = {};\n")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-311.pyc").write_bytes(b"\x00")

    return tmp_path


@pytest.fixture
def sample_file(tmp_path):
    """Create a single Python file with 20 lines for read_file tests."""
    lines = [f"line {i}: content for line {i}" for i in range(1, 21)]
    f = tmp_path / "sample.py"
    f.write_text("\n".join(lines) + "\n")
    return f


@pytest.fixture
def empty_dir(tmp_path):
    """Create an empty directory for edge-case tests."""
    d = tmp_path / "empty"
    d.mkdir()
    return d
