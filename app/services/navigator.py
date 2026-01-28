"""
Code Navigator Service - Fast, incremental code exploration.

Provides CLI-style tools for navigating codebases without loading everything:
- search_code: ripgrep-powered regex search
- read_file: read files with optional line ranges
- list_directory: browse directories with depth control
- find_files: glob-based file finding
"""

import asyncio
import os
import re
import shutil
import subprocess
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# Directories to always skip during traversal
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "vendor", "bower_components",
    ".gradle", ".idea", ".vs", ".vscode", "coverage", ".nyc_output",
    "env", ".env", ".eggs", "*.egg-info",
}

# Max file size to read (1MB)
MAX_READ_SIZE = 1_048_576


@dataclass
class SearchMatch:
    """A single search match."""
    file: str
    line_number: int
    content: str
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result of a code search."""
    pattern: str
    matches: list[SearchMatch]
    total_matches: int
    truncated: bool = False
    error: Optional[str] = None


@dataclass
class FileContent:
    """Content of a read file."""
    path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    size_bytes: int
    language: str
    error: Optional[str] = None


@dataclass
class DirectoryEntry:
    """An entry in a directory listing."""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: list["DirectoryEntry"] = field(default_factory=list)


@dataclass
class FileMatch:
    """A file found by glob search."""
    path: str
    size: int
    extension: str


# Language detection by extension
EXTENSION_TO_LANGUAGE = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "jsx", ".tsx": "tsx", ".java": "java", ".kt": "kotlin",
    ".go": "go", ".rs": "rust", ".c": "c", ".cpp": "cpp", ".h": "c",
    ".hpp": "cpp", ".cs": "csharp", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".scala": "scala", ".r": "r", ".R": "r",
    ".sql": "sql", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".toml": "toml", ".xml": "xml", ".html": "html",
    ".css": "css", ".scss": "scss", ".less": "less", ".md": "markdown",
    ".rst": "rst", ".txt": "text", ".cfg": "ini", ".ini": "ini",
    ".dockerfile": "dockerfile", ".tf": "terraform", ".hcl": "hcl",
    ".proto": "protobuf", ".graphql": "graphql", ".gql": "graphql",
    ".lua": "lua", ".dart": "dart", ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hs": "haskell", ".ml": "ocaml",
    ".vue": "vue", ".svelte": "svelte",
}

# ripgrep file type flags (maps language name to rg --type flag)
RG_TYPE_MAP = {
    "python": "py", "javascript": "js", "typescript": "ts",
    "java": "java", "go": "go", "rust": "rust", "c": "c",
    "cpp": "cpp", "ruby": "ruby", "php": "php", "swift": "swift",
    "scala": "scala", "sql": "sql", "shell": "sh",
    "yaml": "yaml", "json": "json", "toml": "toml",
    "xml": "xml", "html": "html", "css": "css",
    "markdown": "md", "lua": "lua",
    # shorthand aliases
    "py": "py", "js": "js", "ts": "ts", "rb": "ruby",
    "rs": "rust", "md": "md", "sh": "sh",
}


def _has_ripgrep() -> bool:
    """Check if ripgrep (rg) is available on the system."""
    return shutil.which("rg") is not None


def _should_skip(name: str) -> bool:
    """Check if a directory should be skipped."""
    if name in SKIP_DIRS:
        return True
    if name.startswith(".") and name != ".":
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def _detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    # Handle special filenames
    name = Path(file_path).name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    if name in ("cmakelists.txt",):
        return "cmake"
    return EXTENSION_TO_LANGUAGE.get(ext, "")


def _read_file_safe(path: Path) -> str:
    """Read a file with encoding fallback."""
    if path.stat().st_size > MAX_READ_SIZE:
        # Read first chunk only for very large files
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(MAX_READ_SIZE)
        except Exception:
            return "[File too large to read]"

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return "[Unable to read file - encoding error]"
    except Exception as e:
        return f"[Error reading file: {e}]"


async def search_code(
    pattern: str,
    path: str,
    file_type: Optional[str] = None,
    max_results: int = 50,
    context_lines: int = 2,
    ignore_case: bool = False,
) -> SearchResult:
    """
    Search for a regex pattern in code using ripgrep (with Python fallback).

    Args:
        pattern: Regex pattern to search for.
        path: Directory to search in.
        file_type: Optional language filter (e.g., "python", "js", "ts").
        max_results: Maximum number of matches to return.
        context_lines: Lines of context before/after each match.
        ignore_case: Case-insensitive search.

    Returns:
        SearchResult with matches.
    """
    path = os.path.abspath(path)

    if not os.path.isdir(path):
        return SearchResult(
            pattern=pattern, matches=[], total_matches=0,
            error=f"Directory not found: {path}"
        )

    if _has_ripgrep():
        return await _search_with_rg(
            pattern, path, file_type, max_results, context_lines, ignore_case
        )
    else:
        return await _search_with_python(
            pattern, path, file_type, max_results, context_lines, ignore_case
        )


async def _search_with_rg(
    pattern: str,
    path: str,
    file_type: Optional[str],
    max_results: int,
    context_lines: int,
    ignore_case: bool,
) -> SearchResult:
    """Search using ripgrep."""
    cmd = ["rg", "--line-number", "--no-heading", "--color=never"]

    if context_lines > 0:
        cmd.extend(["-C", str(context_lines)])

    if ignore_case:
        cmd.append("-i")

    # Apply file type filter
    if file_type:
        rg_type = RG_TYPE_MAP.get(file_type.lower())
        if rg_type:
            cmd.extend(["--type", rg_type])
        else:
            # Use glob pattern for unknown types
            cmd.extend(["--glob", f"*.{file_type}"])

    # Skip common junk directories
    for skip in ["node_modules", ".git", "__pycache__", ".venv", "venv",
                  "dist", "build", ".next", "target"]:
        cmd.extend(["--glob", f"!{skip}"])

    cmd.extend(["--max-count", str(max_results * 2)])  # Get more than needed, dedup later
    cmd.extend([pattern, path])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=30
        )

        if process.returncode not in (0, 1):  # rg returns 1 for no matches
            # Might be a regex error, try fixed-string search
            cmd_fixed = [c for c in cmd]
            # Insert --fixed-strings before the pattern
            pattern_idx = cmd_fixed.index(pattern)
            cmd_fixed.insert(pattern_idx, "--fixed-strings")

            process = await asyncio.create_subprocess_exec(
                *cmd_fixed,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=30
            )

        output = stdout.decode("utf-8", errors="replace")
        return _parse_rg_output(pattern, output, path, max_results, context_lines)

    except asyncio.TimeoutError:
        return SearchResult(
            pattern=pattern, matches=[], total_matches=0,
            error="Search timed out after 30 seconds"
        )
    except Exception as e:
        return SearchResult(
            pattern=pattern, matches=[], total_matches=0,
            error=f"Search failed: {e}"
        )


def _parse_rg_output(
    pattern: str,
    output: str,
    base_path: str,
    max_results: int,
    context_lines: int,
) -> SearchResult:
    """Parse ripgrep output into SearchResult."""
    if not output.strip():
        return SearchResult(pattern=pattern, matches=[], total_matches=0)

    matches: list[SearchMatch] = []
    current_file = None
    current_match = None
    collecting_after = False
    after_count = 0

    for line in output.split("\n"):
        if not line.strip():
            continue

        # Separator between match groups
        if line == "--":
            if current_match:
                matches.append(current_match)
                current_match = None
            collecting_after = False
            continue

        # Context line (before or after match)
        ctx_match = re.match(r"^(.+?)-(\d+)-(.*)$", line)
        # Match line
        match_line = re.match(r"^(.+?):(\d+):(.*)$", line)

        if match_line:
            # Save previous match
            if current_match and collecting_after:
                matches.append(current_match)

            file_path = match_line.group(1)
            line_num = int(match_line.group(2))
            content = match_line.group(3)

            # Make path relative
            try:
                rel_path = os.path.relpath(file_path, base_path)
            except ValueError:
                rel_path = file_path

            current_match = SearchMatch(
                file=rel_path,
                line_number=line_num,
                content=content,
            )
            collecting_after = True
            after_count = 0

        elif ctx_match and current_match and collecting_after:
            content = ctx_match.group(3)
            after_count += 1
            if after_count <= context_lines:
                current_match.context_after.append(content)

        elif ctx_match and not collecting_after:
            # Context before - we'll attach it to the next match
            pass

    # Don't forget the last match
    if current_match:
        matches.append(current_match)

    truncated = len(matches) > max_results
    matches = matches[:max_results]

    return SearchResult(
        pattern=pattern,
        matches=matches,
        total_matches=len(matches),
        truncated=truncated,
    )


async def _search_with_python(
    pattern: str,
    path: str,
    file_type: Optional[str],
    max_results: int,
    context_lines: int,
    ignore_case: bool,
) -> SearchResult:
    """Fallback search using Python (when ripgrep is not available)."""
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        # If regex is invalid, try as literal string
        regex = re.compile(re.escape(pattern), flags)

    # Determine extensions to filter
    ext_filter = None
    if file_type:
        lang = file_type.lower()
        for ext, lang_name in EXTENSION_TO_LANGUAGE.items():
            if lang_name == lang or ext.lstrip(".") == lang:
                ext_filter = ext_filter or set()
                ext_filter.add(ext)

    matches: list[SearchMatch] = []
    total_found = 0

    for root, dirs, files in os.walk(path):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if not _should_skip(d)]

        for filename in files:
            if total_found >= max_results:
                break

            file_path = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            # Apply extension filter
            if ext_filter and ext not in ext_filter:
                continue

            # Skip binary/large files
            try:
                size = os.path.getsize(file_path)
                if size > MAX_READ_SIZE or size == 0:
                    continue
            except OSError:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if regex.search(line):
                    rel_path = os.path.relpath(file_path, path)

                    ctx_before = []
                    ctx_after = []
                    if context_lines > 0:
                        start = max(0, i - context_lines)
                        ctx_before = [l.rstrip("\n") for l in lines[start:i]]
                        end = min(len(lines), i + context_lines + 1)
                        ctx_after = [l.rstrip("\n") for l in lines[i + 1:end]]

                    matches.append(SearchMatch(
                        file=rel_path,
                        line_number=i + 1,
                        content=line.rstrip("\n"),
                        context_before=ctx_before,
                        context_after=ctx_after,
                    ))
                    total_found += 1
                    if total_found >= max_results:
                        break

    return SearchResult(
        pattern=pattern,
        matches=matches,
        total_matches=len(matches),
        truncated=total_found >= max_results,
    )


def read_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> FileContent:
    """
    Read a file with optional line range.

    Args:
        path: Absolute or relative file path.
        start_line: Starting line number (1-indexed, inclusive).
        end_line: Ending line number (1-indexed, inclusive).

    Returns:
        FileContent with the file contents.
    """
    path = os.path.abspath(path)
    file_path = Path(path)

    if not file_path.exists():
        return FileContent(
            path=path, content="", start_line=0, end_line=0,
            total_lines=0, size_bytes=0, language="",
            error=f"File not found: {path}"
        )

    if not file_path.is_file():
        return FileContent(
            path=path, content="", start_line=0, end_line=0,
            total_lines=0, size_bytes=0, language="",
            error=f"Not a file: {path}"
        )

    size = file_path.stat().st_size
    language = _detect_language(path)
    content = _read_file_safe(file_path)
    lines = content.split("\n")
    total_lines = len(lines)

    # Apply line range
    if start_line is not None or end_line is not None:
        s = max(1, start_line or 1)
        e = min(total_lines, end_line or total_lines)
        selected = lines[s - 1:e]

        # Add line numbers
        numbered = []
        for i, line in enumerate(selected, start=s):
            numbered.append(f"{i:>6}\t{line}")
        content = "\n".join(numbered)
        return FileContent(
            path=path, content=content,
            start_line=s, end_line=e,
            total_lines=total_lines, size_bytes=size,
            language=language,
        )
    else:
        # Add line numbers to full content
        numbered = []
        for i, line in enumerate(lines, start=1):
            numbered.append(f"{i:>6}\t{line}")
        content = "\n".join(numbered)
        return FileContent(
            path=path, content=content,
            start_line=1, end_line=total_lines,
            total_lines=total_lines, size_bytes=size,
            language=language,
        )


def list_directory(
    path: str,
    depth: int = 2,
    show_hidden: bool = False,
    max_entries: int = 200,
) -> tuple[list[DirectoryEntry], int]:
    """
    List directory contents with depth control.

    Args:
        path: Directory path.
        depth: Maximum depth to traverse (1 = immediate children only).
        show_hidden: Whether to show hidden files/dirs.
        max_entries: Maximum total entries to return.

    Returns:
        Tuple of (entries, total_count).
    """
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return [], 0

    count = [0]  # mutable counter for nested function

    def _walk(dir_path: str, current_depth: int) -> list[DirectoryEntry]:
        if current_depth > depth or count[0] >= max_entries:
            return []

        entries = []
        try:
            items = sorted(os.listdir(dir_path))
        except PermissionError:
            return []

        for name in items:
            if count[0] >= max_entries:
                break

            if not show_hidden and name.startswith("."):
                continue

            full_path = os.path.join(dir_path, name)

            if os.path.isdir(full_path):
                if _should_skip(name):
                    continue
                count[0] += 1
                children = _walk(full_path, current_depth + 1) if current_depth < depth else []
                entries.append(DirectoryEntry(
                    name=name,
                    path=os.path.relpath(full_path, path),
                    is_dir=True,
                    children=children,
                ))
            else:
                count[0] += 1
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                entries.append(DirectoryEntry(
                    name=name,
                    path=os.path.relpath(full_path, path),
                    is_dir=False,
                    size=size,
                ))

        return entries

    entries = _walk(path, 1)
    return entries, count[0]


def find_files(
    pattern: str,
    path: str,
    max_results: int = 100,
) -> list[FileMatch]:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts", "*.json").
        path: Base directory to search from.
        max_results: Maximum number of results.

    Returns:
        List of matching files.
    """
    path = os.path.abspath(path)
    base = Path(path)

    if not base.is_dir():
        return []

    results: list[FileMatch] = []

    try:
        for match in base.glob(pattern):
            if len(results) >= max_results:
                break

            if not match.is_file():
                continue

            # Skip files in ignored directories
            rel = match.relative_to(base)
            if any(_should_skip(part) for part in rel.parts[:-1]):
                continue

            try:
                size = match.stat().st_size
            except OSError:
                size = 0

            results.append(FileMatch(
                path=str(rel),
                size=size,
                extension=match.suffix.lower(),
            ))
    except Exception:
        # Fallback: manual walk + fnmatch
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not _should_skip(d)]
            for filename in files:
                if len(results) >= max_results:
                    break
                full = os.path.join(root, filename)
                rel = os.path.relpath(full, path)
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(filename, pattern):
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    results.append(FileMatch(
                        path=rel,
                        size=size,
                        extension=os.path.splitext(filename)[1].lower(),
                    ))

    return results


def format_tree(entries: list[DirectoryEntry], prefix: str = "") -> str:
    """Format directory entries as a tree string."""
    lines = []
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "`-- " if is_last else "|-- "
        child_prefix = "    " if is_last else "|   "

        if entry.is_dir:
            lines.append(f"{prefix}{connector}{entry.name}/")
            if entry.children:
                lines.append(format_tree(entry.children, prefix + child_prefix))
        else:
            size_str = _format_size(entry.size)
            lines.append(f"{prefix}{connector}{entry.name} ({size_str})")

    return "\n".join(lines)


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"
