"""
Code Loader Tool - Clones and loads GitHub repositories.

RESPONSIBILITY:
Downloads/clones a GitHub repository to local storage so other
tools can access and process the code files.

FLOW:
1. Receive repository URL
2. Parse URL to extract owner/repo
3. Clone to local storage (or use cached copy)
4. Return path to cloned repository
"""

import os
import hashlib
from pathlib import Path

from app.agents.base import BaseTool, AgentContext, ToolResult, ToolType


class CodeLoaderTool(BaseTool):
    """
    Clones GitHub repositories to local storage.

    Features:
    - Caches repositories to avoid re-cloning
    - Validates repository URLs
    - Handles clone failures gracefully
    """

    name = ToolType.CODE_LOADER.value
    description = "Clones a GitHub repository to local storage"

    def __init__(self, storage_path: str = "./repos"):
        """
        Initialize the code loader.

        Args:
            storage_path: Base directory for storing cloned repos
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def execute(self, context: AgentContext, **kwargs) -> ToolResult:
        """
        Clone the repository specified in context.

        Args:
            context: Contains repo_url to clone

        Returns:
            ToolResult with path to cloned repo
        """
        repo_url = kwargs.get("repo_url") or context.repo_url

        if not repo_url:
            return ToolResult(
                success=False,
                error="No repository URL provided"
            )

        context.log(f"CodeLoader: Loading repository {repo_url}")

        try:
            # Generate unique path for this repo
            repo_path = self._get_repo_path(repo_url)

            # Check if already cloned
            if repo_path.exists() and self._is_valid_repo(repo_path):
                context.log("CodeLoader: Using cached repository")
                context.repo_path = str(repo_path)
                return ToolResult(
                    success=True,
                    data={"path": str(repo_path), "cached": True}
                )

            # Clone the repository
            await self._clone_repo(repo_url, repo_path)

            context.repo_path = str(repo_path)
            return ToolResult(
                success=True,
                data={"path": str(repo_path), "cached": False}
            )

        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}"
            context.add_error(error_msg)
            return ToolResult(success=False, error=error_msg)

    def _get_repo_path(self, repo_url: str) -> Path:
        """
        Generate a unique local path for a repository.

        Uses hash of URL to create consistent, unique directory names.
        """
        # Create hash of URL for unique folder name
        url_hash = hashlib.md5(repo_url.encode()).hexdigest()[:12]

        # Extract repo name from URL
        repo_name = repo_url.rstrip("/").split("/")[-1]
        repo_name = repo_name.replace(".git", "")

        return self.storage_path / f"{repo_name}_{url_hash}"

    def _is_valid_repo(self, path: Path) -> bool:
        """Check if path contains a valid git repository."""
        git_dir = path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    async def _clone_repo(self, repo_url: str, target_path: Path) -> None:
        """
        Clone repository using git.

        In production, this would use asyncio subprocess or gitpython.
        """
        import subprocess

        # Remove existing directory if present
        if target_path.exists():
            import shutil
            shutil.rmtree(target_path)

        # Clone with depth=1 for faster cloning (shallow clone)
        cmd = ["git", "clone", "--depth", "1", repo_url, str(target_path)]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if process.returncode != 0:
            raise RuntimeError(f"Git clone failed: {process.stderr}")
