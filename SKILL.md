---
name: scout-code-navigator
description: Explore, search, and understand any codebase using Scout MCP tools. Use when the user asks to analyze a GitHub repo, find where a function is defined, understand how a codebase works, read specific files, or explore local project structure. Triggers on phrases like "explore this repo", "how does X work in this codebase", "find where Y is defined", "analyze https://github.com/...", "what does this project do".
metadata:
  author: MayankSethi27
  version: "3.0.1"
---

# Scout Code Navigator

Scout is an MCP server that gives you 5 code navigation tools to explore any codebase — local directories or GitHub URLs — without hitting context limits or copy-pasting files manually.

## Setup (Required Before First Use)

Before Scout's tools are available, the MCP server must be installed and connected. If the user tries to use Scout and the tools aren't responding, run these steps automatically:

**Step 1 — Install the Scout MCP server:**
```bash
pip install pipx
python -m pipx ensurepath
pipx install scout-code-navigator
```

**Step 2 — Connect Scout to Claude Code:**
```bash
claude mcp add scout -s user -- scout
```

**Step 3 — Verify it's connected:**
```bash
claude mcp list
```
Scout should appear in the list. If it does, the tools (`repo_overview`, `search_code`, `read_file`, `list_directory`, `find_files`) are now available.

> **Note for Claude Desktop users:** Instead of Step 2, add this to your `claude_desktop_config.json`:
> ```json
> { "mcpServers": { "scout": { "command": "scout", "args": [] } } }
> ```
> Then restart Claude Desktop.

Once setup is complete, proceed with the tools below.

## When to Use Each Tool

Use tools **incrementally** — don't try to read everything at once. Navigate like a developer would.

### `repo_overview` — Always start here
Call this first when exploring any unfamiliar codebase. Returns directory tree, README, detected tech stack, file counts, and entry points.

```
repo_overview({ path: "/local/path" })
repo_overview({ path: "https://github.com/owner/repo" })
```

### `search_code` — Find patterns across the entire codebase
Use to locate function definitions, class declarations, imports, or any regex pattern. Powered by ripgrep — fast even on 100k+ file repos.

```
search_code({ query: "def authenticate", path: "/repo", file_type: "python" })
search_code({ query: "import.*jwt", path: "/repo", ignore_case: true })
search_code({ query: "TODO|FIXME", path: "/repo", max_results: 100 })
```

`file_type` accepts: `python`, `js`, `ts`, `go`, `rust`, `java`, `ruby`, `sql`, `yaml`, `json`, etc.

### `read_file` — Read a specific file (with line ranges)
Use after `search_code` returns a match to read the surrounding context. Always use line ranges on large files rather than reading the whole file.

```
read_file({ path: "/repo/src/auth.py" })
read_file({ path: "/repo/src/auth.py", start_line: 45, end_line: 120 })
```

### `list_directory` — Browse a specific directory
Use to understand a subdirectory's structure before deciding which files to read.

```
list_directory({ path: "/repo/src", depth: 3 })
```

### `find_files` — Locate files by name pattern
Use when you need to find all files of a certain type or matching a naming convention.

```
find_files({ pattern: "**/*.test.ts", path: "/repo" })
find_files({ pattern: "**/models.py", path: "/repo" })
find_files({ pattern: "docker-compose*.yml", path: "/repo" })
```

## Recommended Exploration Pattern

For most codebase questions, follow this sequence:

1. **`repo_overview`** → understand the structure and stack
2. **`search_code`** → find the relevant code by pattern
3. **`read_file`** with line ranges → read the specific sections
4. **`list_directory`** or **`find_files`** if you need to locate more related files

## GitHub URL Support

Scout automatically shallow-clones GitHub repos on first use and caches them for 24 hours. Both public and private repos work — private repos use your existing git credentials.

```
repo_overview({ path: "https://github.com/django/django" })
search_code({ query: "class Model", path: "https://github.com/django/django", file_type: "python" })
```

> Note: For GitHub URLs, pass the URL only to `repo_overview` first. The response includes the `Local path:` where Scout cloned it — use that local path for all subsequent `search_code`, `read_file`, and other calls to avoid re-cloning on every request.

## Tips

- Prefer `search_code` over reading entire directories — it's faster and more precise
- Use `file_type` filtering to narrow searches to the relevant language
- Use `start_line`/`end_line` in `read_file` when you already know the relevant section from a search result
- `max_results` defaults to 50 for search and 100 for find_files — increase if you need broader coverage
