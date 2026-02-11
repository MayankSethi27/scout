"""Tests for app.services.overview — repository overview service."""

import json
import os

import pytest

from app.services.overview import (
    _detect_stack,
    _find_and_read_readme,
    _find_config_files,
    _find_entry_points,
    _get_file_stats,
    get_overview,
)

# ── get_overview ─────────────────────────────────────────────────────────────


class TestGetOverview:
    def test_basic_overview(self, sample_project):
        ov = get_overview(str(sample_project))
        assert ov.error is None
        assert ov.name == sample_project.name
        assert ov.tree  # non-empty tree string
        assert ov.readme != "(No README found)"

    def test_nonexistent_dir(self, tmp_path):
        ov = get_overview(str(tmp_path / "nope"))
        assert ov.error is not None
        assert "not found" in ov.error.lower()

    def test_tree_depth_parameter(self, sample_project):
        shallow = get_overview(str(sample_project), tree_depth=1)
        deep = get_overview(str(sample_project), tree_depth=4)
        # Deeper tree should generally produce a longer string
        assert len(deep.tree) >= len(shallow.tree)


# ── find_and_read_readme ─────────────────────────────────────────────────────


class TestFindAndReadReadme:
    def test_finds_readme_md(self, sample_project):
        content = _find_and_read_readme(str(sample_project))
        assert "Test Project" in content

    def test_no_readme(self, empty_dir):
        content = _find_and_read_readme(str(empty_dir))
        assert content == "(No README found)"

    def test_lowercase_readme(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Lower\n")
        content = _find_and_read_readme(str(tmp_path))
        assert "Lower" in content

    def test_long_readme_truncated(self, tmp_path):
        (tmp_path / "README.md").write_text("x" * 6000)
        content = _find_and_read_readme(str(tmp_path))
        assert "truncated" in content.lower()
        assert len(content) < 6000


# ── detect_stack ─────────────────────────────────────────────────────────────


class TestDetectStack:
    def test_detects_python(self, sample_project):
        stack = _detect_stack(str(sample_project))
        assert "Python" in stack.languages

    def test_detects_js_frameworks(self, sample_project):
        stack = _detect_stack(str(sample_project))
        assert "React" in stack.frameworks
        assert "Vite" in stack.frameworks

    def test_detects_docker(self, sample_project):
        stack = _detect_stack(str(sample_project))
        assert "Docker" in stack.tools

    def test_detects_docker_compose(self, sample_project):
        stack = _detect_stack(str(sample_project))
        assert "Docker Compose" in stack.tools

    def test_detects_python_frameworks(self, sample_project):
        stack = _detect_stack(str(sample_project))
        assert "FastAPI" in stack.frameworks

    def test_empty_dir(self, empty_dir):
        stack = _detect_stack(str(empty_dir))
        assert stack.languages == []
        assert stack.frameworks == []
        assert stack.tools == []


# ── get_file_stats ───────────────────────────────────────────────────────────


class TestGetFileStats:
    def test_counts_files(self, sample_project):
        stats = _get_file_stats(str(sample_project))
        assert stats["total_files"] > 0

    def test_top_extensions_include_py(self, sample_project):
        stats = _get_file_stats(str(sample_project))
        exts = [ext for ext, _ in stats["top_extensions"]]
        assert ".py" in exts

    def test_skips_node_modules(self, sample_project):
        stats = _get_file_stats(str(sample_project))
        # node_modules has lodash.js; if skipped, .js count should be low
        ext_map = dict(stats["top_extensions"])
        # app.js is the only non-skipped .js file
        assert ext_map.get(".js", 0) <= 2

    def test_empty_dir(self, empty_dir):
        stats = _get_file_stats(str(empty_dir))
        assert stats["total_files"] == 0


# ── find_entry_points ────────────────────────────────────────────────────────


class TestFindEntryPoints:
    def test_finds_main_py(self, sample_project):
        ep = _find_entry_points(str(sample_project))
        assert "main.py" in ep

    def test_empty_dir(self, empty_dir):
        ep = _find_entry_points(str(empty_dir))
        assert ep == []


# ── find_config_files ────────────────────────────────────────────────────────


class TestFindConfigFiles:
    def test_finds_config_files(self, sample_project):
        configs = _find_config_files(str(sample_project))
        assert "pyproject.toml" in configs
        assert "Dockerfile" in configs
        assert "Makefile" in configs
        assert "docker-compose.yml" in configs
        assert ".gitignore" in configs

    def test_empty_dir(self, empty_dir):
        configs = _find_config_files(str(empty_dir))
        assert configs == []
