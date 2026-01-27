"""
Repository Service - Manages GitHub repository operations.

RESPONSIBILITY:
Handles all repository-related operations including:
- URL parsing and validation
- Cloning repositories
- Caching and cleanup
- Repository metadata extraction
"""

import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import re


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
    storage_path: str = "./repos"
    max_repo_size_mb: int = 500
    cache_ttl_hours: int = 24
    clone_timeout_seconds: int = 300
    shallow_clone: bool = True


class RepoService:
    """
    Service for managing GitHub repositories.

    Features:
    - Clone repositories with caching
    - Parse GitHub URLs
    - Manage repository lifecycle
    - Extract repository metadata

    Usage:
        service = RepoService(config)
        repo_info = await service.clone("https://github.com/owner/repo")
        files = service.list_files(repo_info.local_path)
    """

    # Regex patterns for GitHub URLs
    GITHUB_PATTERNS = [
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/?",
    ]

    def __init__(self, config: Optional[RepoServiceConfig] = None):
        """
        Initialize repository service.

        Args:
            config: Service configuration
        """
        self.config = config or RepoServiceConfig()
        self.storage_path = Path(self.config.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._repo_cache: Dict[str, RepoInfo] = {}

    def parse_github_url(self, url: str) -> RepoInfo:
        """
        Parse a GitHub URL into components.

        Args:
            url: GitHub repository URL

        Returns:
            RepoInfo with parsed components

        Raises:
            ValueError: If URL is not a valid GitHub URL
        """
        url = url.strip()

        for pattern in self.GITHUB_PATTERNS:
            match = re.match(pattern, url)
            if match:
                groups = match.groups()
                owner = groups[0]
                name = groups[1].replace(".git", "")
                branch = groups[2] if len(groups) > 2 else None

                return RepoInfo(
                    owner=owner,
                    name=name,
                    url=f"https://github.com/{owner}/{name}",
                    branch=branch
                )

        raise ValueError(f"Invalid GitHub URL: {url}")

    async def clone(
        self,
        url: str,
        force: bool = False
    ) -> RepoInfo:
        """
        Clone a GitHub repository.

        Args:
            url: GitHub repository URL
            force: Force re-clone even if cached

        Returns:
            RepoInfo with local path populated
        """
        repo_info = self.parse_github_url(url)

        # Check cache
        cache_key = self._get_cache_key(repo_info)
        if not force and cache_key in self._repo_cache:
            cached = self._repo_cache[cache_key]
            if cached.local_path and Path(cached.local_path).exists():
                if self._is_cache_valid(cached):
                    return cached

        # Generate local path
        local_path = self._get_local_path(repo_info)

        # Clone repository
        await self._clone_repo(repo_info, local_path)

        # Update repo info
        repo_info.local_path = str(local_path)
        repo_info.cloned_at = datetime.now()

        # Cache the result
        self._repo_cache[cache_key] = repo_info

        return repo_info

    async def _clone_repo(self, repo_info: RepoInfo, target_path: Path) -> None:
        """Execute git clone command."""
        # Remove existing directory
        if target_path.exists():
            shutil.rmtree(target_path)

        # Build clone command
        cmd = ["git", "clone"]

        if self.config.shallow_clone:
            cmd.extend(["--depth", "1"])

        if repo_info.branch:
            cmd.extend(["--branch", repo_info.branch])

        cmd.extend([repo_info.url, str(target_path)])

        # Execute clone
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.clone_timeout_seconds
            )
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(
                f"Clone timed out after {self.config.clone_timeout_seconds}s"
            )

        if process.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode()}")

    def _get_local_path(self, repo_info: RepoInfo) -> Path:
        """Generate unique local path for repository."""
        # Create hash for uniqueness
        url_hash = hashlib.md5(repo_info.url.encode()).hexdigest()[:8]
        folder_name = f"{repo_info.owner}_{repo_info.name}_{url_hash}"
        return self.storage_path / folder_name

    def _get_cache_key(self, repo_info: RepoInfo) -> str:
        """Generate cache key for repository."""
        return f"{repo_info.owner}/{repo_info.name}"

    def _is_cache_valid(self, repo_info: RepoInfo) -> bool:
        """Check if cached repository is still valid."""
        if not repo_info.cloned_at:
            return False

        ttl = timedelta(hours=self.config.cache_ttl_hours)
        return datetime.now() - repo_info.cloned_at < ttl

    def list_files(
        self,
        repo_path: str,
        extensions: Optional[List[str]] = None
    ) -> List[Path]:
        """
        List all files in a repository.

        Args:
            repo_path: Path to cloned repository
            extensions: Optional list of extensions to filter

        Returns:
            List of file paths
        """
        repo_path = Path(repo_path)
        files = []

        # Directories to skip
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv",
            "venv", "dist", "build", ".next", "target"
        }

        for file_path in repo_path.rglob("*"):
            if file_path.is_dir():
                continue

            # Skip files in ignored directories
            if any(skip in file_path.parts for skip in skip_dirs):
                continue

            # Filter by extension if specified
            if extensions and file_path.suffix.lower() not in extensions:
                continue

            files.append(file_path)

        return files

    def get_file_content(self, file_path: str) -> str:
        """
        Read file content with encoding handling.

        Args:
            file_path: Path to file

        Returns:
            File content as string
        """
        path = Path(file_path)

        # Try UTF-8 first
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            pass

        # Fallback to latin-1
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return ""

    def get_repo_stats(self, repo_path: str) -> Dict[str, Any]:
        """
        Get statistics about a repository.

        Args:
            repo_path: Path to cloned repository

        Returns:
            Dict with file counts, sizes, languages
        """
        repo_path = Path(repo_path)
        files = self.list_files(repo_path)

        # Count by extension
        extension_counts: Dict[str, int] = {}
        total_size = 0

        for file in files:
            ext = file.suffix.lower() or "no_extension"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

            try:
                total_size += file.stat().st_size
            except OSError:
                pass

        return {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "extensions": extension_counts,
            "top_extensions": sorted(
                extension_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }

    async def cleanup(self, repo_url: str) -> bool:
        """
        Remove a cloned repository.

        Args:
            repo_url: Repository URL to clean up

        Returns:
            True if cleanup successful
        """
        try:
            repo_info = self.parse_github_url(repo_url)
            cache_key = self._get_cache_key(repo_info)

            if cache_key in self._repo_cache:
                cached = self._repo_cache[cache_key]
                if cached.local_path and Path(cached.local_path).exists():
                    shutil.rmtree(cached.local_path)
                del self._repo_cache[cache_key]

            return True
        except Exception:
            return False

    async def cleanup_expired(self) -> int:
        """
        Remove all expired cached repositories.

        Returns:
            Number of repositories cleaned up
        """
        cleaned = 0
        expired_keys = []

        for key, repo_info in self._repo_cache.items():
            if not self._is_cache_valid(repo_info):
                if repo_info.local_path and Path(repo_info.local_path).exists():
                    shutil.rmtree(repo_info.local_path)
                expired_keys.append(key)
                cleaned += 1

        for key in expired_keys:
            del self._repo_cache[key]

        return cleaned
