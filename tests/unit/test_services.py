"""Tests for app.services.navigator — code navigation tools."""

import os
from unittest.mock import patch

import pytest

from app.services.navigator import (
    DirectoryEntry,
    _detect_language,
    _format_size,
    _parse_rg_output,
    _should_skip,
    find_files,
    format_tree,
    list_directory,
    read_file,
    search_code,
)

# ── detect_language ──────────────────────────────────────────────────────────


class TestDetectLanguage:
    def test_python(self):
        assert _detect_language("main.py") == "python"

    def test_typescript(self):
        assert _detect_language("app.ts") == "typescript"

    def test_tsx(self):
        assert _detect_language("Button.tsx") == "tsx"

    def test_unknown_extension(self):
        assert _detect_language("data.xyz") == ""

    def test_dockerfile(self):
        assert _detect_language("Dockerfile") == "dockerfile"

    def test_makefile(self):
        assert _detect_language("Makefile") == "makefile"

    def test_cmakelists(self):
        assert _detect_language("CMakeLists.txt") == "cmake"


# ── should_skip ──────────────────────────────────────────────────────────────


class TestShouldSkip:
    def test_git(self):
        assert _should_skip(".git") is True

    def test_node_modules(self):
        assert _should_skip("node_modules") is True

    def test_hidden_directory(self):
        assert _should_skip(".hidden") is True

    def test_egg_info(self):
        assert _should_skip("my_pkg.egg-info") is True

    def test_normal_directory(self):
        assert _should_skip("src") is False


# ── format_size ──────────────────────────────────────────────────────────────


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(512) == "512B"

    def test_kilobytes(self):
        result = _format_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_size(2 * 1024 * 1024)
        assert "MB" in result

    def test_zero(self):
        assert _format_size(0) == "0B"


# ── read_file ────────────────────────────────────────────────────────────────


class TestReadFile:
    def test_full_file(self, sample_file):
        result = read_file(str(sample_file))
        assert result.error is None
        assert result.total_lines == 21  # 20 content lines + trailing newline
        assert result.language == "python"
        assert "line 1:" in result.content

    def test_line_range(self, sample_file):
        result = read_file(str(sample_file), start_line=5, end_line=10)
        assert result.error is None
        assert result.start_line == 5
        assert result.end_line == 10
        assert "line 5:" in result.content

    def test_nonexistent(self, tmp_path):
        result = read_file(str(tmp_path / "nope.txt"))
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_directory_error(self, tmp_path):
        result = read_file(str(tmp_path))
        assert result.error is not None
        assert "not a file" in result.error.lower()

    def test_language_detection(self, tmp_path):
        ts_file = tmp_path / "index.ts"
        ts_file.write_text("const x = 1;\n")
        result = read_file(str(ts_file))
        assert result.language == "typescript"

    def test_start_only(self, sample_file):
        result = read_file(str(sample_file), start_line=15)
        assert result.start_line == 15
        assert result.error is None

    def test_end_only(self, sample_file):
        result = read_file(str(sample_file), end_line=5)
        assert result.start_line == 1
        assert result.end_line == 5
        assert result.error is None


# ── list_directory ───────────────────────────────────────────────────────────


class TestListDirectory:
    def test_basic_listing(self, sample_project):
        entries, total = list_directory(str(sample_project), depth=1)
        assert total > 0
        names = [e.name for e in entries]
        assert "main.py" in names
        assert "src" in names

    def test_skips_node_modules_git_pycache(self, sample_project):
        entries, _ = list_directory(str(sample_project), depth=3)
        all_names = _collect_names(entries)
        assert "node_modules" not in all_names
        assert "__pycache__" not in all_names

    def test_depth_control(self, sample_project):
        entries_d1, _ = list_directory(str(sample_project), depth=1)
        entries_d3, _ = list_directory(str(sample_project), depth=3)
        # Depth 1 shouldn't have nested children
        for e in entries_d1:
            if e.is_dir:
                assert e.children == []

        # Depth 3 should have deeper nesting
        src = next((e for e in entries_d3 if e.name == "src"), None)
        assert src is not None
        assert len(src.children) > 0

    def test_nonexistent(self, tmp_path):
        entries, total = list_directory(str(tmp_path / "nope"))
        assert entries == []
        assert total == 0

    def test_empty_dir(self, empty_dir):
        entries, total = list_directory(str(empty_dir))
        assert entries == []
        assert total == 0

    def test_max_entries(self, sample_project):
        entries, total = list_directory(str(sample_project), depth=3, max_entries=3)
        assert total <= 3

    def test_entry_types(self, sample_project):
        entries, _ = list_directory(str(sample_project), depth=1)
        dirs = [e for e in entries if e.is_dir]
        files = [e for e in entries if not e.is_dir]
        assert len(dirs) > 0
        assert len(files) > 0


# ── find_files ───────────────────────────────────────────────────────────────


class TestFindFiles:
    def test_find_python_files(self, sample_project):
        results = find_files("**/*.py", str(sample_project))
        paths = [r.path for r in results]
        assert any("main.py" in p for p in paths)

    def test_find_ts_tsx(self, sample_project):
        ts = find_files("**/*.ts", str(sample_project))
        tsx = find_files("**/*.tsx", str(sample_project))
        assert len(ts) > 0
        assert len(tsx) > 0

    def test_skips_node_modules(self, sample_project):
        results = find_files("**/*.js", str(sample_project))
        for r in results:
            assert "node_modules" not in r.path

    def test_nonexistent_dir(self, tmp_path):
        results = find_files("**/*.py", str(tmp_path / "nope"))
        assert results == []

    def test_max_results(self, sample_project):
        results = find_files("**/*", str(sample_project), max_results=2)
        assert len(results) <= 2

    def test_no_matches(self, sample_project):
        results = find_files("**/*.zzz", str(sample_project))
        assert results == []


# ── format_tree ──────────────────────────────────────────────────────────────


class TestFormatTree:
    def test_basic_tree(self):
        entries = [
            DirectoryEntry(name="file.py", path="file.py", is_dir=False, size=100),
            DirectoryEntry(name="dir", path="dir", is_dir=True, children=[]),
        ]
        tree = format_tree(entries)
        assert "file.py" in tree
        assert "dir/" in tree

    def test_empty_entries(self):
        assert format_tree([]) == ""

    def test_nested_tree(self):
        child = DirectoryEntry(
            name="inner.py", path="dir/inner.py", is_dir=False, size=50
        )
        parent = DirectoryEntry(name="dir", path="dir", is_dir=True, children=[child])
        tree = format_tree([parent])
        assert "dir/" in tree
        assert "inner.py" in tree


# ── search_code (Python fallback) ───────────────────────────────────────────


class TestSearchCodePythonFallback:
    """Test search_code with ripgrep disabled to exercise Python fallback."""

    @pytest.fixture(autouse=True)
    def disable_ripgrep(self):
        with patch("app.services.navigator._has_ripgrep", return_value=False):
            yield

    @pytest.mark.asyncio
    async def test_basic_search(self, sample_project):
        result = await search_code("hello", str(sample_project))
        assert result.error is None
        assert result.total_matches > 0

    @pytest.mark.asyncio
    async def test_regex_search(self, sample_project):
        result = await search_code(r"def \w+", str(sample_project))
        assert result.total_matches > 0

    @pytest.mark.asyncio
    async def test_case_insensitive(self, sample_project):
        result = await search_code("HELLO", str(sample_project), ignore_case=True)
        assert result.total_matches > 0

    @pytest.mark.asyncio
    async def test_file_type_filter(self, sample_project):
        result = await search_code("import", str(sample_project), file_type="python")
        for m in result.matches:
            assert m.file.endswith(".py")

    @pytest.mark.asyncio
    async def test_max_results(self, sample_project):
        result = await search_code(".", str(sample_project), max_results=2)
        assert len(result.matches) <= 2

    @pytest.mark.asyncio
    async def test_context_lines(self, sample_project):
        result = await search_code("def add", str(sample_project), context_lines=1)
        if result.matches:
            m = result.matches[0]
            assert isinstance(m.context_after, list)

    @pytest.mark.asyncio
    async def test_nonexistent_dir(self, tmp_path):
        result = await search_code("test", str(tmp_path / "nope"))
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_no_matches(self, sample_project):
        result = await search_code("zzzzz_no_match_zzzzz", str(sample_project))
        assert result.total_matches == 0

    @pytest.mark.asyncio
    async def test_invalid_regex_fallback(self, sample_project):
        # Invalid regex should fall back to literal match
        result = await search_code("[invalid", str(sample_project))
        assert result.error is None  # Should not error, uses re.escape

    @pytest.mark.asyncio
    async def test_skips_node_modules(self, sample_project):
        result = await search_code("module.exports", str(sample_project))
        for m in result.matches:
            assert "node_modules" not in m.file


# ── parse_rg_output ──────────────────────────────────────────────────────────


class TestParseRgOutput:
    def test_simple_match(self):
        output = "/base/file.py:10:def hello():\n"
        result = _parse_rg_output("hello", output, "/base", 50, 0)
        assert len(result.matches) == 1
        assert result.matches[0].line_number == 10
        assert result.matches[0].file == "file.py"

    def test_empty_output(self):
        result = _parse_rg_output("test", "", "/base", 50, 0)
        assert len(result.matches) == 0

    def test_multiple_matches(self):
        output = "/base/a.py:1:foo\n/base/b.py:2:bar\n"
        result = _parse_rg_output("test", output, "/base", 50, 0)
        assert len(result.matches) == 2

    def test_truncation(self):
        lines = "".join(f"/base/f.py:{i}:line\n" for i in range(1, 20))
        result = _parse_rg_output("test", lines, "/base", 5, 0)
        assert result.truncated is True
        assert len(result.matches) == 5


# ── helpers ──────────────────────────────────────────────────────────────────


def _collect_names(entries):
    """Recursively collect all names from directory entries."""
    names = []
    for e in entries:
        names.append(e.name)
        if e.children:
            names.extend(_collect_names(e.children))
    return names
