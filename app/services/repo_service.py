"""
Repository Service - Resolves local paths and clones remote repos.

Handles:
- Parsing GitHub URLs
- Shallow cloning remote repos (cached)
- Resolving a user input (local path or GitHub URL) to a local directory
"""

import asyncio
import hashlib
import shutil
import stat
import os
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import re


def _remove_readonly(func, path, excinfo):
    """Error handler for shutil.rmtree on Windows (read-only .git files)."""
    import time
    exc_type = excinfo[0] if excinfo else None
    if exc_type in (PermissionError, OSError):
        for attempt in range(3):
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
                return
            except (PermissionError, OSError):
                time.sleep(0.1 * (attempt + 1))
            except Exception:
                break


def _safe_rmtree(path: Path) -> None:
    """Safely remove a directory tree, handling Windows permission issues."""
    import gc
    if not path.exists():
        return
    gc.collect()
    for attempt in range(3):
        try:
            shutil.rmtree(path, onerror=_remove_readonly)
            return
        except (PermissionError, OSError):
            if attempt < 2:
                import time
                time.sleep(0.5 * (attempt + 1))
                gc.collect()


@dataclass
class RepoInfo:
    """Parsed repository information."""
    owner: str
    name: str
    url: str
    branch: Optional[str] = None
    local_path: Optional[str] = None
    cloned_at: Optional[datetime] = None


@dataclass
class RepoServiceConfig:
    """Configuration for repository service."""
    storage_path: str = "./data/repos"
    cache_ttl_hours: int = 24
    clone_timeout_seconds: int = 300
    shallow_clone: bool = True


# Regex patterns for GitHub URLs
_GITHUB_PATTERNS = [
    r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
    r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/?",
]


def is_github_url(path_or_url: str) -> bool:
    """Check if the input looks like a GitHub URL."""
    return bool(
        path_or_url.startswith("https://github.com/")
        or path_or_url.startswith("http://github.com/")
        or path_or_url.startswith("git@github.com:")
    )


def parse_github_url(url: str) -> RepoInfo:
    """Parse a GitHub URL into components."""
    url = url.strip()
    for pattern in _GITHUB_PATTERNS:
        match = re.match(pattern, url)
        if match:
            groups = match.groups()
            owner = groups[0]
            name = groups[1].replace(".git", "")
            branch = groups[2] if len(groups) > 2 else None
            return RepoInfo(
                owner=owner, name=name,
                url=f"https://github.com/{owner}/{name}",
                branch=branch,
            )
    raise ValueError(f"Invalid GitHub URL: {url}")


class RepoService:
    """
    Resolves paths for code navigation.

    For local paths: validates and returns as-is.
    For GitHub URLs: shallow clones with caching, returns local path.
    """

    def __init__(self, config: Optional[RepoServiceConfig] = None):
        self.config = config or RepoServiceConfig()
        self.storage_path = Path(self.config.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, RepoInfo] = {}

    async def resolve_path(self, path_or_url: str) -> str:
        """
        Resolve a local path or GitHub URL to a local directory path.

        Args:
            path_or_url: Either a local directory path or a GitHub URL.

        Returns:
            Absolute local path to the repository.

        Raises:
            ValueError: If the path doesn't exist or URL is invalid.
        """
        if is_github_url(path_or_url):
            repo_info = await self.clone(path_or_url)
            return repo_info.local_path
        else:
            # Local path
            local = os.path.abspath(path_or_url)
            if not os.path.isdir(local):
                raise ValueError(f"Directory not found: {local}")
            return local

    async def clone(self, url: str, force: bool = False) -> RepoInfo:
        """Shallow clone a GitHub repository (cached)."""
        repo_info = parse_github_url(url)
        cache_key = f"{repo_info.owner}/{repo_info.name}"

        # Check cache
        if not force and cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.local_path and Path(cached.local_path).exists():
                if self._is_cache_valid(cached):
                    return cached

        local_path = self._get_local_path(repo_info)

        # Clone with retry
        last_error = None
        for attempt in range(3):
            try:
                await self._execute_clone(repo_info, local_path)
                break
            except (TimeoutError, RuntimeError) as e:
                last_error = e
                if attempt < 2:
                    if local_path.exists():
                        _safe_rmtree(local_path)
                    await asyncio.sleep(2 ** attempt)
        else:
            raise last_error

        repo_info.local_path = str(local_path)
        repo_info.cloned_at = datetime.now()
        self._cache[cache_key] = repo_info
        return repo_info

    async def _execute_clone(self, repo_info: RepoInfo, target: Path) -> None:
        """Execute a shallow git clone."""
        if target.exists():
            _safe_rmtree(target)

        cmd = ["git", "clone", "--depth", "1", "--single-branch", "--no-tags"]
        if repo_info.branch:
            cmd.extend(["--branch", repo_info.branch])
        cmd.extend([repo_info.url, str(target)])

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.clone_timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Clone timed out after {self.config.clone_timeout_seconds}s")

        if process.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode()}")

    def _get_local_path(self, repo_info: RepoInfo) -> Path:
        url_hash = hashlib.md5(repo_info.url.encode()).hexdigest()[:8]
        return self.storage_path / f"{repo_info.owner}_{repo_info.name}_{url_hash}"

    def _is_cache_valid(self, info: RepoInfo) -> bool:
        if not info.cloned_at:
            return False
        ttl = timedelta(hours=self.config.cache_ttl_hours)
        return datetime.now() - info.cloned_at < ttl

    async def cleanup(self, url: str) -> bool:
        """Remove a cloned repository."""
        try:
            info = parse_github_url(url)
            key = f"{info.owner}/{info.name}"
            if key in self._cache:
                cached = self._cache[key]
                if cached.local_path and Path(cached.local_path).exists():
                    _safe_rmtree(Path(cached.local_path))
                del self._cache[key]
            return True
        except Exception:
            return False
