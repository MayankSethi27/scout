# Scout

Give Claude the power to understand any GitHub codebase instantly.

An MCP server that enables Claude to analyze any GitHub repository using semantic code search. Just paste a GitHub URL and ask questions.

**Works with:** Claude Desktop, Claude Code CLI

### Why not just paste a GitHub URL into ChatGPT/Claude?

| | Pasting URL directly | This MCP Tool |
|---|---|---|
| **Access to code** | Can only see README or limited files | Searches entire codebase |
| **Large repos** | Hits context limits quickly | Handles repos of any size |
| **Accuracy** | Often hallucinates code | Returns actual code snippets |
| **Private repos** | No access | Works with your git credentials |
| **Speed** | Must re-read each time | Indexed and cached locally |

### Features
- **100% Local** - No API keys needed, all processing on your machine
- **Semantic Search** - Finds code by meaning, not just keywords
- **Fast** - Index once (~30s), query instantly (~0.01s)
- **Private Repos** - Works with your git credentials
- **20+ Languages** - Python, JS, TS, Go, Rust, Java, C++, and more

## Quick Start (2 Steps)

### Step 1: Install

**Using pipx (handles PATH automatically)**
```bash
# Step 1: Install pipx
pip install pipx

# Step 2: Add pipx to your PATH
python -m pipx ensurepath

# Step 3: Close and reopen your terminal (required!)

# Step 4: Install github-code-retrieval
pipx install github-code-retrieval
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
       "github-code-retrieval": {
         "command": "github-code-retrieval",
         "args": []
       }
     }
   }
   ```

   > **Note:** If you already have other MCP servers configured, just add the `"github-code-retrieval"` entry inside the existing `"mcpServers"` object.

3. **Restart Claude Desktop** to apply changes.

---

#### Claude Code CLI

```bash
#  Register with Claude Code CLI
claude mcp add github-code-retrieval -s user -- github-code-retrieval
```

The `-s user` flag adds it at user scope, so it works in any directory.

> **If you get "command not found"** after Step 3, see [Troubleshooting](#command-not-found-github-code-retrieval) for alternative commands.

**For HTTP server mode:**
```bash
claude mcp add --transport http github-code-retrieval http://localhost:8000
```

**Verify Installation**

After setup, verify the MCP server is connected:

- **Claude Desktop:** Look for the tool icon in the chat interface
- **Claude Code CLI:** Run `/mcp` to see connected servers

## Usage

Once configured, just ask Claude to analyze any GitHub repo:

```
"Analyze https://github.com/pallets/flask and explain how routing works"

"How does authentication work in https://github.com/tiangolo/fastapi?"

"Find the database connection code in https://github.com/django/django"
```

Claude will automatically use the tool to:
1. Clone the repository
2. Index all code files locally
3. Search for relevant code snippets
4. Return the most relevant code to answer your question

## Features

- **No API Keys** - Everything runs locally on your machine
- **Semantic Search** - Finds code by meaning, not just keywords
- **Fast** - First query indexes the repo (~30s), subsequent queries are instant (~0.01s)
- **Private Repos** - Works with private repos if you have git credentials set up
- **20+ Languages** - Python, JavaScript, TypeScript, Go, Rust, Java, and more

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  You: "How does routing work in this Flask app?"               │
│                              │                                  │
│                              ▼                                  │
│  Claude calls: analyze_github_repo(                            │
│      repo_url="https://github.com/pallets/flask",              │
│      question="How does routing work?"                         │
│  )                                                             │
│                              │                                  │
│                              ▼                                  │
│  MCP Server (runs locally on your machine):                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 1. Clone repo (cached for 24h)                            │ │
│  │ 2. Index code with local embeddings (sentence-transformers)│ │
│  │ 3. Semantic search (ChromaDB)                             │ │
│  │ 4. Return top relevant code snippets                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  Claude receives code snippets and explains them to you        │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration (Optional)

Create a `.env` file to customize settings:

```bash
# Embedding model (default: all-MiniLM-L6-v2)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Device for embeddings: cpu, cuda (NVIDIA), mps (Apple Silicon)
EMBEDDING_DEVICE=cpu

# Storage paths
VECTOR_STORE_PATH=./data/vector_db
REPO_STORAGE_PATH=./data/repos

# Indexing settings
CHUNK_SIZE=1500
CHUNK_OVERLAP=200
```

## GPU Acceleration

For faster embeddings:

**NVIDIA GPU:**
```bash
EMBEDDING_DEVICE=cuda
```

**Apple Silicon:**
```bash
EMBEDDING_DEVICE=mps
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

If you want to run the server on a network (e.g., shared team server):

```bash
# Start HTTP server
github-code-retrieval-http

# Server runs on http://0.0.0.0:8000
# API docs at http://localhost:8000/docs
```

Then configure clients to connect:
```json
{
  "mcpServers": {
    "github-code-retrieval": {
      "command": "http",
      "args": ["http://SERVER_IP:8000"]
    }
  }
}
```


## Troubleshooting

### "Command not found: github-code-retrieval"

This happens when Python's Scripts folder isn't in your PATH. Choose one of these solutions:

**Solution 1: Use pipx (Recommended)**
```bash
pip install pipx
pipx ensurepath
pipx install github-code-retrieval
# Restart your terminal
```

**Solution 2: Add Scripts folder to PATH**

Find your Scripts folder:
```bash
python -m site --user-base
```

Then add the Scripts subfolder to your PATH:

| OS | Typical Scripts Location |
|----|-------------------------|
| Windows | `C:\Users\<username>\AppData\Roaming\Python\Python3XX\Scripts` |
| macOS/Linux | `~/.local/bin` |

**Solution 3: Use full path in config**

Find the full path to the executable:
```bash
# Windows (PowerShell)
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"

# macOS/Linux
which github-code-retrieval || python -m site --user-base
```

Then use the full path in your config:
```json
{
  "mcpServers": {
    "github-code-retrieval": {
      "command": "C:/Users/YourName/AppData/Roaming/Python/Python313/Scripts/github-code-retrieval.exe",
      "args": []
    }
  }
}
```

**Solution 4: Use python -m (Always works)**
```json
{
  "mcpServers": {
    "github-code-retrieval": {
      "command": "python",
      "args": ["-m", "mcp_stdio_server"]
    }
  }
}
```

For Claude Code CLI with python -m:
```bash
claude mcp add github-code-retrieval -s user -- python -m mcp_stdio_server
```

### Out of memory
Large repos may need more RAM. Try:
- Reducing `CHUNK_SIZE` in `.env`
- Using a smaller embedding model

## Development

```bash
# Clone the repo
git clone https://github.com/yourusername/github-code-retrieval
cd github-code-retrieval

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```
