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

```bash
pip install github-code-retrieval
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

**Option A: Using the CLI command (Recommended)**

Run this single command to add the MCP server globally:

```bash
claude mcp add github-code-retrieval -s user
```
```bash
 # For HTTP server
  claude mcp add --transport http github-code-retrieval http://localhost:8000
```

The `-s user` flag adds it at user scope, so it works in any directory.

**Option B: Manual configuration**

Add to your config file:

| Scope | Config File Location |
|-------|---------------------|
| Global (user) | `~/.claude.json` (macOS/Linux) or `C:\Users\<username>\.claude.json` (Windows) |
| Project-specific | `.claude.json` in your project directory |

Add this to the config file:

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

Then restart Claude Code CLI.

---

**Verify Installation**

After setup, verify the MCP server is connected:

- **Claude Desktop:** Look for the tool icon in the chat interface
- **Claude Code CLI:** Run `/mcp` to see connected servers
- **Cursor:** Check the MCP status in the bottom status bar

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

## Tool Schema

The MCP server exposes one tool: `analyze_github_repo`

**Input:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "question": "How does authentication work?",
  "top_k": 10
}
```

**Output:**
```json
{
  "success": true,
  "repository": {
    "url": "https://github.com/owner/repo",
    "owner": "owner",
    "name": "repo",
    "total_files_indexed": 45,
    "total_chunks": 230
  },
  "query": "How does authentication work?",
  "code_snippets": [
    {
      "file_path": "src/auth/handler.py",
      "content": "def authenticate(request):\n    ...",
      "start_line": 45,
      "end_line": 78,
      "language": "python",
      "relevance_score": 0.89
    }
  ],
  "total_results": 10
}
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

## Supported Languages

Python, JavaScript, TypeScript, JSX, TSX, Java, Kotlin, Go, Rust, C, C++, C#, Ruby, PHP, Swift, Scala, SQL, GraphQL, YAML, JSON, TOML, Markdown, and more.

## Troubleshooting

### "Command not found: github-code-retrieval"
Make sure pip's bin directory is in your PATH:
```bash
# Find where pip installs scripts
python -m site --user-base
# Add that path + /bin to your PATH
```

Or use the full path:
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

### Slow first query
The first query for a repo takes ~30-60 seconds to:
1. Clone the repository
2. Load the embedding model (~400MB)
3. Index all code files

Subsequent queries are fast (~0.01s).

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

## License

MIT
