"""
Repository Overview Service - Quick high-level understanding of a codebase.

Scans a repository to provide:
- Directory tree structure
- README content
- Stack detection (languages, frameworks, tools)
- File statistics
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from app.services.navigator import (
    list_directory,
    format_tree,
    SKIP_DIRS,
    EXTENSION_TO_LANGUAGE,
)


# Config files that reveal the stack
STACK_INDICATORS = {
    # Python
    "pyproject.toml": {"language": "Python"},
    "setup.py": {"language": "Python"},
    "setup.cfg": {"language": "Python"},
    "requirements.txt": {"language": "Python"},
    "Pipfile": {"language": "Python", "tool": "Pipenv"},
    "poetry.lock": {"language": "Python", "tool": "Poetry"},
    "tox.ini": {"language": "Python", "tool": "tox"},
    # JavaScript / TypeScript
    "package.json": {"language": "JavaScript/TypeScript"},
    "tsconfig.json": {"language": "TypeScript"},
    "yarn.lock": {"tool": "Yarn"},
    "pnpm-lock.yaml": {"tool": "pnpm"},
    "package-lock.json": {"tool": "npm"},
    "bun.lockb": {"tool": "Bun"},
    # Go
    "go.mod": {"language": "Go"},
    "go.sum": {"language": "Go"},
    # Rust
    "Cargo.toml": {"language": "Rust"},
    "Cargo.lock": {"language": "Rust"},
    # Java / Kotlin
    "pom.xml": {"language": "Java", "tool": "Maven"},
    "build.gradle": {"language": "Java/Kotlin", "tool": "Gradle"},
    "build.gradle.kts": {"language": "Kotlin", "tool": "Gradle"},
    # Ruby
    "Gemfile": {"language": "Ruby"},
    "Gemfile.lock": {"language": "Ruby", "tool": "Bundler"},
    # PHP
    "composer.json": {"language": "PHP", "tool": "Composer"},
    # C / C++
    "CMakeLists.txt": {"language": "C/C++", "tool": "CMake"},
    "Makefile": {"tool": "Make"},
    # .NET
    "*.csproj": {"language": "C#", "tool": ".NET"},
    "*.fsproj": {"language": "F#", "tool": ".NET"},
    "*.sln": {"tool": ".NET"},
    # Elixir
    "mix.exs": {"language": "Elixir", "tool": "Mix"},
    # Dart / Flutter
    "pubspec.yaml": {"language": "Dart"},
    # Docker
    "Dockerfile": {"tool": "Docker"},
    "docker-compose.yml": {"tool": "Docker Compose"},
    "docker-compose.yaml": {"tool": "Docker Compose"},
    # CI/CD
    ".github/workflows": {"tool": "GitHub Actions"},
    ".gitlab-ci.yml": {"tool": "GitLab CI"},
    "Jenkinsfile": {"tool": "Jenkins"},
    ".circleci/config.yml": {"tool": "CircleCI"},
    # Config
    ".eslintrc.js": {"tool": "ESLint"},
    ".eslintrc.json": {"tool": "ESLint"},
    ".prettierrc": {"tool": "Prettier"},
    "tailwind.config.js": {"framework": "Tailwind CSS"},
    "tailwind.config.ts": {"framework": "Tailwind CSS"},
}

# Framework detection from package.json dependencies
JS_FRAMEWORKS = {
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "angular": "Angular",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "express": "Express.js",
    "fastify": "Fastify",
    "hono": "Hono",
    "koa": "Koa",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "remix": "Remix",
    "gatsby": "Gatsby",
    "astro": "Astro",
    "electron": "Electron",
    "prisma": "Prisma",
    "@prisma/client": "Prisma",
    "drizzle-orm": "Drizzle ORM",
    "mongoose": "Mongoose",
    "typeorm": "TypeORM",
    "tailwindcss": "Tailwind CSS",
    "vite": "Vite",
    "webpack": "Webpack",
    "esbuild": "esbuild",
    "jest": "Jest",
    "vitest": "Vitest",
    "mocha": "Mocha",
    "playwright": "Playwright",
    "cypress": "Cypress",
}

# Framework detection from Python deps
PY_FRAMEWORKS = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "sanic": "Sanic",
    "aiohttp": "aiohttp",
    "celery": "Celery",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "pytest": "pytest",
    "numpy": "NumPy",
    "pandas": "pandas",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "transformers": "Hugging Face Transformers",
    "scrapy": "Scrapy",
    "boto3": "AWS SDK",
    "langchain": "LangChain",
    "openai": "OpenAI SDK",
}


@dataclass
class StackInfo:
    """Detected technology stack."""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


@dataclass
class RepoOverview:
    """Complete repository overview."""
    path: str
    name: str
    tree: str
    readme: str
    stack: StackInfo
    file_stats: dict
    entry_points: list[str]
    config_files: list[str]
    error: Optional[str] = None


def get_overview(path: str, tree_depth: int = 3) -> RepoOverview:
    """
    Generate a high-level overview of a repository.

    Args:
        path: Path to the repository root.
        tree_depth: Depth for directory tree (default 3).

    Returns:
        RepoOverview with all detected information.
    """
    path = os.path.abspath(path)

    if not os.path.isdir(path):
        return RepoOverview(
            path=path, name="", tree="", readme="",
            stack=StackInfo(), file_stats={},
            entry_points=[], config_files=[],
            error=f"Directory not found: {path}",
        )

    name = os.path.basename(path)

    # Build directory tree
    entries, total = list_directory(path, depth=tree_depth, max_entries=300)
    tree = f"{name}/\n{format_tree(entries)}"

    # Read README
    readme = _find_and_read_readme(path)

    # Detect stack
    stack = _detect_stack(path)

    # Get file stats
    file_stats = _get_file_stats(path)

    # Find entry points
    entry_points = _find_entry_points(path)

    # List config files in root
    config_files = _find_config_files(path)

    return RepoOverview(
        path=path,
        name=name,
        tree=tree,
        readme=readme,
        stack=stack,
        file_stats=file_stats,
        entry_points=entry_points,
        config_files=config_files,
    )


def _find_and_read_readme(path: str) -> str:
    """Find and read the README file."""
    readme_names = [
        "README.md", "readme.md", "README", "README.txt",
        "README.rst", "Readme.md", "README.MD",
    ]

    for name in readme_names:
        readme_path = os.path.join(path, name)
        if os.path.isfile(readme_path):
            try:
                with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                # Truncate very long READMEs
                if len(content) > 5000:
                    content = content[:5000] + "\n\n... (truncated)"
                return content
            except Exception:
                continue

    return "(No README found)"


def _detect_stack(path: str) -> StackInfo:
    """Detect the technology stack from config files."""
    languages = set()
    frameworks = set()
    tools = set()

    # Check for known indicator files
    for indicator, info in STACK_INDICATORS.items():
        indicator_path = os.path.join(path, indicator)
        if os.path.exists(indicator_path):
            if "language" in info:
                languages.add(info["language"])
            if "framework" in info:
                frameworks.add(info["framework"])
            if "tool" in info:
                tools.add(info["tool"])

    # Check .github/workflows directory
    workflows_path = os.path.join(path, ".github", "workflows")
    if os.path.isdir(workflows_path):
        tools.add("GitHub Actions")

    # Parse package.json for JS frameworks
    pkg_json_path = os.path.join(path, "package.json")
    if os.path.isfile(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            all_deps = {}
            all_deps.update(pkg.get("dependencies", {}))
            all_deps.update(pkg.get("devDependencies", {}))

            for dep, framework in JS_FRAMEWORKS.items():
                if dep in all_deps:
                    frameworks.add(framework)
        except Exception:
            pass

    # Parse requirements.txt for Python frameworks
    req_path = os.path.join(path, "requirements.txt")
    if os.path.isfile(req_path):
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip().lower()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # Extract package name (before version specifier)
                    pkg_name = line.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].split("[")[0].strip()
                    if pkg_name in PY_FRAMEWORKS:
                        frameworks.add(PY_FRAMEWORKS[pkg_name])
        except Exception:
            pass

    # Parse pyproject.toml for Python frameworks (simple parsing)
    pyproject_path = os.path.join(path, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read().lower()
            for dep, framework in PY_FRAMEWORKS.items():
                if f'"{dep}' in content or f"'{dep}" in content:
                    frameworks.add(framework)
        except Exception:
            pass

    return StackInfo(
        languages=sorted(languages),
        frameworks=sorted(frameworks),
        tools=sorted(tools),
    )


def _get_file_stats(path: str) -> dict:
    """Get file count statistics by extension."""
    ext_counts: dict[str, int] = {}
    total_files = 0
    total_size = 0

    for root, dirs, files in os.walk(path):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in files:
            try:
                full_path = os.path.join(root, filename)
                size = os.path.getsize(full_path)
                total_files += 1
                total_size += size
                ext = os.path.splitext(filename)[1].lower() or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            except OSError:
                continue

    # Sort by count, take top 15
    top_extensions = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "top_extensions": top_extensions,
    }


def _find_entry_points(path: str) -> list[str]:
    """Find likely entry point files."""
    entry_names = [
        "main.py", "app.py", "server.py", "index.py", "manage.py", "wsgi.py",
        "index.js", "app.js", "server.js", "main.js",
        "index.ts", "app.ts", "server.ts", "main.ts",
        "main.go", "cmd/main.go",
        "main.rs", "lib.rs",
        "Main.java", "Application.java", "App.java",
        "index.html",
        "main.c", "main.cpp",
    ]

    found = []
    for name in entry_names:
        # Check root
        full = os.path.join(path, name)
        if os.path.isfile(full):
            found.append(name)
            continue

        # Check src/
        src_full = os.path.join(path, "src", name)
        if os.path.isfile(src_full):
            found.append(f"src/{name}")

    return found


def _find_config_files(path: str) -> list[str]:
    """List configuration files in the root directory."""
    config_extensions = {
        ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".env", ".config", ".rc",
    }
    config_names = {
        "Makefile", "Dockerfile", "Procfile", "Vagrantfile",
        "Rakefile", "Gemfile", "Pipfile",
        ".gitignore", ".dockerignore", ".editorconfig",
        ".env.example", ".env.sample",
    }

    configs = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(name)[1].lower()
            if name in config_names or ext in config_extensions:
                configs.append(name)
    except OSError:
        pass

    return configs
