# Scout 

**Give Claude the ability to actually read, search, and understand any codebase.**

**Works with:** Claude Desktop | Claude Code CLI

---

## What is Scout?

Scout is an [MCP server](https://modelcontextprotocol.io/) that solves a fundamental problem: **Claude can reason about code, but it can't see your code.** When you ask Claude about a repository, it's guessing based on general knowledge - it has no way to browse the directory structure, search for a function definition, or read a specific file.

Scout fixes this. It gives Claude a set of code navigation tools - the same actions a developer takes when exploring an unfamiliar codebase:

1. **Look at the project structure** - What's in this repo? What tech stack is it using?
2. **Search for patterns** - Where is `authenticate` defined? Which files import `database`?
3. **Read specific code** - Show me lines 50-100 of `auth.py`
4. **Find files** - Where are all the `*.test.ts` files?

No embeddings, no vector databases, no indexing step. Scout uses [ripgrep](https://github.com/BurntSushi/ripgrep) for fast regex search and direct file access - the same approach experienced developers use, just wired into Claude via MCP.

## The Problem

When you paste a GitHub URL into ChatGPT or Claude, the model can only see the README (if that). It can't browse the repo, search code, or read files. For any real question about how code works, you end up manually copying and pasting file contents into the chat - which breaks down completely on large repos.

| | Pasting URLs into chat | Scout |
|---|---|---|
| **Code access** | README only, maybe a few files | Full codebase - every file, every line |
| **Large repos** | Hits context limits fast | Handles 100k+ files efficiently |
| **Accuracy** | Hallucinates function signatures and file paths | Returns actual code with real line numbers |
| **Private repos** | No access at all | Uses your local git credentials |
| **Workflow** | You copy-paste code manually | Claude searches and reads code autonomously |

## Why not just use GitHub CLI?

GitHub CLI (`gh`) **manages** repos (PRs, issues, releases). Scout **understands** code. Different tools, different jobs:

- `gh` talks to GitHub's API - Scout runs locally with no rate limits
- `gh` can't do regex search with context lines - Scout uses ripgrep across the entire codebase
- `gh` isn't an MCP server - Scout is, so Claude calls it autonomously
- `gh` doesn't work on local directories - Scout works on both local and GitHub repos

**They're complementary.** Use `gh` to manage repos. Use Scout to let Claude read the code inside them.

## Features

- **No API Keys** - Everything runs locally on your machine
- **No Indexing** - Start exploring immediately, zero setup wait
- **Fast** - Regex search powered by ripgrep, even on massive codebases
- **Private Repos** - Uses your existing git credentials
- **20+ Languages** - Python, JS, TS, Go, Rust, Java, C++, and more
- **Lightweight** - 6 dependencies, minimal footprint, instant startup
- **Works Anywhere** - Local directories, GitHub URLs, or both

## Quick Start

### Step 1: Install

```bash
pip install pipx
python -m pipx ensurepath
# Close and reopen your terminal after this

pipx install scout-code-navigator
```

### Step 2: Add to Claude

Choose your platform:

---

#### Claude Desktop

1. Open the Claude Desktop config file:

   | OS | Config File Location |
   |----|---------------------|
   | macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
   | Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
   | Linux | `~/.config/claude/claude_desktop_config.json` |

2. Add the MCP server configuration:

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

   > **Note:** If you already have other MCP servers configured, just add the `"scout"` entry inside the existing `"mcpServers"` object.

3. **Restart Claude Desktop** to apply changes.

---

#### Claude Code CLI

```bash
claude mcp add scout -s user -- scout
```

The `-s user` flag adds it at user scope, so it works in any directory.

---

#### Verify Installation

After setup, verify the MCP server is connected:

- **Claude Desktop:** Look for the tool icon in the chat interface
- **Claude Code CLI:** Run `/mcp` to see connected servers

> **If you get "command not found"** after install, see [Troubleshooting](#command-not-found-scout) below.

## Tools

Scout provides 5 tools that Claude uses automatically:

| Tool | Description |
|------|-------------|
| `repo_overview` | High-level overview: directory tree, README, tech stack detection, file stats, entry points |
| `list_directory` | Browse directory contents with depth control (1-10 levels) |
| `search_code` | Regex search across the codebase using ripgrep, with file type filtering |
| `read_file` | Read file contents with optional line range selection |
| `find_files` | Find files by glob pattern (e.g., `**/*.py`, `src/**/*.ts`) |

## Usage

Once configured, just ask Claude to analyze any repo:

```
"Analyze https://github.com/pallets/flask and explain how routing works"

"How does authentication work in https://github.com/tiangolo/fastapi?"

"Find the database models in https://github.com/django/django"

"Explore my local project at /path/to/my/project"
```

## How It Works

```
You: "How does routing work in this Flask app?"
                         |
                         v
Claude calls tools incrementally:
+-----------------------------------------------------------+
| 1. repo_overview  -> directory tree, README, tech stack   |
| 2. search_code    -> ripgrep search for "def route"       |
| 3. read_file      -> read matching files with line ranges |
+-----------------------------------------------------------+
                         |
                         v
Claude receives actual code snippets and explains them to you
```

No indexing step, no embedding computation. Claude navigates the code like a developer would - browsing structure, searching for patterns, and reading relevant files.

## Configuration (Optional)

Create a `.env` file to customize settings:

```bash
# Application
APP_NAME="Scout Code Navigator"
DEBUG=false

# HTTP Server (only for scout-http mode)
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Repository cloning (GitHub URLs only, local repos need no config)
REPO_STORAGE_PATH=~/.scout/repos
REPO_CACHE_TTL_HOURS=24
REPO_CLONE_TIMEOUT_SECONDS=300
```

## Private Repositories

The tool uses your system's git credentials. To access private repos:

```bash
# Option 1: GitHub CLI (recommended)
gh auth login

# Option 2: SSH key
# Just make sure your SSH key is set up for GitHub

# Option 3: Credential helper
git config --global credential.helper store
```

## Alternative: HTTP Server Mode

Run the server over HTTP for shared/team use:

```bash
# Start HTTP server
scout-http

# Server runs on http://0.0.0.0:8000
# API docs at http://localhost:8000/docs
```

Then configure Claude Code CLI to connect:
```bash
claude mcp add --transport http scout http://localhost:8000
```

## Troubleshooting

**"Command not found: scout"** - Python's Scripts folder isn't in your PATH. Easiest fix:

```bash
pipx install scout-code-navigator   # pipx handles PATH automatically
```

Or bypass PATH entirely using `python -m`:
```json
{ "mcpServers": { "scout": { "command": "python", "args": ["-m", "mcp_stdio_server"] } } }
```
```bash
# Claude Code CLI equivalent
claude mcp add scout -s user -- python -m mcp_stdio_server
```

**Ripgrep not found** - Scout falls back to Python search automatically, but for best performance install [ripgrep](https://github.com/BurntSushi/ripgrep): `brew install ripgrep` (macOS), `apt install ripgrep` (Ubuntu), `scoop install ripgrep` (Windows).

## Development

```bash
# Clone the repo
git clone https://github.com/MayankSethi27/scout.git
cd scout

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run MCP server locally
python mcp_stdio_server.py

# Run HTTP server locally
python mcp_server.py
```

## Tech Stack

- **Python 3.10+** with async/await
- **MCP SDK** (Model Context Protocol)
- **FastAPI** + **Uvicorn** for HTTP mode
- **Pydantic** for data validation
- **Ripgrep** for fast regex search (optional, has Python fallback)

## License

- MIT
- Claude Code
