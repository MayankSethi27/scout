# Scout — MCP Code Navigator

**Give Claude the ability to actually read, search, and understand any codebase.**

**Works with:** Claude Desktop · Claude Code CLI · Any MCP-compatible agent

[![PyPI](https://img.shields.io/pypi/v/scout-code-navigator)](https://pypi.org/project/scout-code-navigator/)
[![Python](https://img.shields.io/pypi/pyversions/scout-code-navigator)](https://pypi.org/project/scout-code-navigator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/MayankSethi27/scout/actions/workflows/ci.yml/badge.svg)](https://github.com/MayankSethi27/scout/actions)

---

## The Problem

When you share a GitHub URL with Claude — or any LLM — it can only see the README, maybe a few files from its training data. It can't browse the directory structure, search for a function definition, or read a specific file. For any real question about how code works, you end up manually copying and pasting file contents into the chat, which breaks down completely on large codebases.

Scout fixes this. It's an [MCP server](https://modelcontextprotocol.io/) that gives Claude the same tools a developer uses to explore an unfamiliar codebase: browse the structure, search for patterns, read specific files.

---

## Why Not Just Use [X]?

### Why not the GitHub CLI (`gh`)?

`gh` **manages** repositories — pull requests, issues, releases, secrets. Scout **reads** code. They solve completely different problems:

| | `gh` CLI | Scout |
|---|---|---|
| Purpose | Manage repos via GitHub API | Navigate and read code locally |
| Code search | No regex search | ripgrep across entire codebase |
| Private repos | Needs GitHub auth token | Uses your existing git credentials |
| Rate limits | GitHub API limits | None — runs fully locally |
| MCP server | No | Yes — Claude calls it autonomously |
| Local-only repos | No | Yes |

### Why not Claude's built-in "Add from GitHub" feature?

Claude's chat UI can pull a repo into context, but it has hard limits:

- Hits context window limits on any medium/large repo
- Loads everything at once — no incremental "look at this file" exploration
- No regex search across the codebase
- Not available in Claude Code CLI or programmatic use
- Claude can't ask for *more* code if it needs to dig deeper

Scout lets Claude navigate code the way a developer would — incrementally browsing structure, searching for patterns, and reading only the relevant files.

### Why not GitHub Copilot's codebase indexing?

Copilot indexes your codebase using embeddings/vector search — which means:

- You wait for indexing before you can search
- Results are semantic approximations, not exact matches
- No line-number precision
- Tied to the Copilot ecosystem

Scout uses direct file access + ripgrep. Zero indexing wait. Exact regex matches with line numbers. Works on any repo, anywhere, with any MCP-compatible agent.

### Why not just paste code into the chat?

This works for small files. It breaks down when:
- The repo has 50+ relevant files
- You don't know which files are relevant yet
- The function you need is buried 4 directories deep
- You hit the context window limit before finding the answer

Scout lets Claude search first, then read only what's relevant.

---

## Features

- **No API Keys** — Runs entirely on your machine
- **No Indexing** — Start exploring immediately, zero setup wait
- **Fast Search** — ripgrep-powered regex across 100k+ file codebases
- **Private Repos** — Uses your existing git credentials
- **GitHub URL Support** — Shallow-clone any public or private repo on first use
- **20+ Languages** — Python, JS, TS, Go, Rust, Java, C++, Ruby, and more
- **Lightweight** — 6 dependencies, ~500 lines of core logic
- **Dual Mode** — stdio for Claude Desktop/CLI, HTTP for team/shared use

---

## Quick Start

### Step 1: Install

```bash
pip install pipx && python -m pipx ensurepath
# Close and reopen your terminal

pipx install scout-code-navigator
```

### Step 2: Connect to Claude

#### Claude Desktop

Open your config file:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

Add the server:

```json
{
  "mcpServers": {
    "scout": {
      "command": "scout",
      "args": []
    }
  }
}
```

Restart Claude Desktop. Done.

#### Claude Code CLI

```bash
claude mcp add scout -s user -- scout
```

The `-s user` flag registers it globally — works in any project directory.

#### Verify

- **Claude Desktop:** Look for the tool icon (hammer) in the chat UI
- **Claude Code CLI:** Run `/mcp` and confirm `scout` appears as connected

---

## Tools

Claude calls these automatically based on your questions:

| Tool | When Claude uses it |
|------|-------------------|
| `repo_overview` | First look at any repo — tree, README, detected stack, file counts |
| `list_directory` | Drilling into a specific subdirectory |
| `search_code` | Finding where a function/class/pattern is defined or used |
| `read_file` | Reading a specific file, optionally just a line range |
| `find_files` | Locating files by name pattern (e.g., all `*.test.ts` files) |

---

## Usage

Once connected, just talk to Claude about code:

```
"Analyze https://github.com/pallets/flask and explain how routing works"

"How does authentication work in this codebase?"

"Find all the database models in https://github.com/django/django"

"Where is the rate limiting logic implemented?"

"Explore my local project at /path/to/my/project and summarize the architecture"
```

Claude will call the tools incrementally — browsing structure, searching for patterns, reading the relevant files — then explain what it finds.

---

## How It Works

```
You ask: "How does routing work in this Flask app?"
                    |
                    v
Claude calls tools in sequence:
┌────────────────────────────────────────────────────────┐
│ 1. repo_overview  → directory tree + README + stack    │
│ 2. search_code    → ripgrep for "def route", "@app."   │
│ 3. read_file      → read matching files at line ranges │
└────────────────────────────────────────────────────────┘
                    |
                    v
Claude explains the actual code to you
```

No embeddings. No vector database. No indexing step. Just direct file access and regex search — the same approach experienced developers use, made available to Claude via MCP.

---

## Configuration

Create a `.env` file in your working directory to override defaults:

```bash
# Repository cloning (GitHub URLs only — local repos need nothing)
REPO_STORAGE_PATH=~/.scout/repos   # Where cloned repos are cached
REPO_CACHE_TTL_HOURS=24            # How long before re-cloning
REPO_CLONE_TIMEOUT_SECONDS=300     # Max time to wait for a clone

# HTTP Server mode only
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

---

## Private Repositories

Scout uses your system's git credentials — whatever works in your terminal works in Scout.

```bash
# Option 1: GitHub CLI (recommended)
gh auth login

# Option 2: SSH key (if already set up, nothing extra needed)

# Option 3: Credential helper
git config --global credential.helper store
```

---

## HTTP Server Mode

For shared team use, run Scout as an HTTP server instead of a local stdio process:

```bash
# Start the server
scout-http
# Runs on http://localhost:8000
# API docs at http://localhost:8000/docs
```

Connect Claude Code CLI to it:

```bash
claude mcp add --transport http scout http://localhost:8000
```

The HTTP server exposes identical functionality to the stdio server — same 5 tools, same behavior — via `POST` endpoints.

---

## Troubleshooting

**"Command not found: scout"**

Python's Scripts directory isn't on your PATH. Use `pipx` (it handles PATH automatically):

```bash
pipx install scout-code-navigator
```

Or bypass PATH entirely:

```json
{
  "mcpServers": {
    "scout": {
      "command": "python",
      "args": ["-m", "mcp_stdio_server"]
    }
  }
}
```

**"Search is slow"**

Scout uses ripgrep when available and falls back to Python search when not. For best performance, install ripgrep:

```bash
brew install ripgrep          # macOS
apt install ripgrep           # Ubuntu/Debian
scoop install ripgrep         # Windows
winget install BurntSushi.ripgrep  # Windows (alternative)
```

**"Clone failed for private repo"**

Run `gh auth login` or ensure your SSH key is set up and test with `git clone <url>` in your terminal first.

---

## Development

```bash
git clone https://github.com/MayankSethi27/scout.git
cd scout
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest

# Run a single test
pytest tests/unit/test_services.py::TestSearchCode

# Format code
black . && isort .

# Run the stdio server locally
python mcp_stdio_server.py

# Run the HTTP server locally
python mcp_server.py
```

---

## Tech Stack

- **Python 3.10+** with async/await
- **[MCP SDK](https://github.com/modelcontextprotocol/python-sdk)** — Model Context Protocol
- **[ripgrep](https://github.com/BurntSushi/ripgrep)** — Fast regex search (optional, Python fallback included)
- **FastAPI** + **Uvicorn** — HTTP server mode
- **Pydantic** — Data validation and settings

---

## License

MIT — see [LICENSE](LICENSE).
