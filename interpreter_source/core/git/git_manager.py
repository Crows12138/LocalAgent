"""
Git manager for LocalAgent.

Provides a high-level interface for Git operations.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GitCommit:
    """Represents a Git commit."""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str


@dataclass
class GitStatus:
    """Represents Git repository status."""
    branch: str
    is_clean: bool
    staged: List[str]
    modified: List[str]
    untracked: List[str]
    deleted: List[str]
    ahead: int = 0
    behind: int = 0


class GitManager:
    """
    Manages Git operations for a repository.

    Usage:
        git = GitManager("./my_project")

        # Get status
        status = git.status()
        print(f"On branch: {status.branch}")

        # View changes
        diff = git.diff()

        # Commit
        git.commit("fix: resolve login bug")
    """

    def __init__(self, repo_path: str = "."):
        """
        Initialize GitManager.

        Args:
            repo_path: Path to the Git repository
        """
        self.repo_path = str(Path(repo_path).resolve())
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Check if the path is a valid Git repository."""
        git_dir = Path(self.repo_path) / ".git"
        if not git_dir.exists():
            raise ValueError(f"Not a Git repository: {self.repo_path}")

    def _run_git(self, *args: str, check: bool = True) -> Tuple[int, str, str]:
        """
        Run a Git command.

        Args:
            *args: Git command arguments
            check: Whether to raise on non-zero exit

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, ["git", *args], result.stdout, result.stderr
                )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Git command timed out: git {' '.join(args)}")
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not in PATH")

    # =========================================================================
    # Status and Info
    # =========================================================================

    def status(self) -> GitStatus:
        """
        Get repository status.

        Returns:
            GitStatus object with current state
        """
        # Get branch name
        _, branch_out, _ = self._run_git("branch", "--show-current")
        branch = branch_out.strip() or "HEAD"

        # Get status
        _, status_out, _ = self._run_git("status", "--porcelain", "-b")
        lines = status_out.strip().split("\n") if status_out.strip() else []

        staged = []
        modified = []
        untracked = []
        deleted = []
        ahead = 0
        behind = 0

        for line in lines:
            if line.startswith("##"):
                # Parse branch info
                if "ahead" in line:
                    try:
                        ahead = int(line.split("ahead ")[1].split("]")[0].split(",")[0])
                    except (IndexError, ValueError):
                        pass
                if "behind" in line:
                    try:
                        behind = int(line.split("behind ")[1].split("]")[0])
                    except (IndexError, ValueError):
                        pass
                continue

            if len(line) < 3:
                continue

            index_status = line[0]
            worktree_status = line[1]
            filename = line[3:]

            # Staged changes
            if index_status in "MADRC":
                staged.append(filename)

            # Working tree changes
            if worktree_status == "M":
                modified.append(filename)
            elif worktree_status == "D":
                deleted.append(filename)
            elif worktree_status == "?":
                untracked.append(filename)

        is_clean = not (staged or modified or untracked or deleted)

        return GitStatus(
            branch=branch,
            is_clean=is_clean,
            staged=staged,
            modified=modified,
            untracked=untracked,
            deleted=deleted,
            ahead=ahead,
            behind=behind,
        )

    def diff(self, staged: bool = False, file: Optional[str] = None) -> str:
        """
        Get diff of changes.

        Args:
            staged: If True, show staged changes; otherwise unstaged
            file: Specific file to diff (optional)

        Returns:
            Diff output string
        """
        args = ["diff"]
        if staged:
            args.append("--cached")
        if file:
            args.extend(["--", file])

        _, stdout, _ = self._run_git(*args)
        return stdout

    def log(
        self,
        count: int = 10,
        oneline: bool = False,
        file: Optional[str] = None,
    ) -> List[GitCommit]:
        """
        Get commit history.

        Args:
            count: Number of commits to retrieve
            oneline: Use compact format
            file: Show commits for specific file

        Returns:
            List of GitCommit objects
        """
        format_str = "%H|%h|%an|%ad|%s"
        args = ["log", f"-{count}", f"--format={format_str}", "--date=short"]

        if file:
            args.extend(["--", file])

        _, stdout, _ = self._run_git(*args)

        commits = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) >= 5:
                commits.append(GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    author=parts[2],
                    date=parts[3],
                    message=parts[4],
                ))

        return commits

    def show(self, commit: str = "HEAD") -> str:
        """
        Show details of a commit.

        Args:
            commit: Commit hash or reference

        Returns:
            Commit details and diff
        """
        _, stdout, _ = self._run_git("show", commit)
        return stdout

    # =========================================================================
    # Staging and Committing
    # =========================================================================

    def add(self, files: Optional[List[str]] = None, all: bool = False) -> None:
        """
        Stage files for commit.

        Args:
            files: List of files to stage
            all: Stage all changes
        """
        if all:
            self._run_git("add", "-A")
        elif files:
            self._run_git("add", "--", *files)
        else:
            raise ValueError("Must specify files or all=True")

    def unstage(self, files: Optional[List[str]] = None) -> None:
        """
        Unstage files.

        Args:
            files: Files to unstage (None = all)
        """
        if files:
            self._run_git("reset", "HEAD", "--", *files)
        else:
            self._run_git("reset", "HEAD")

    def commit(self, message: str, add_all: bool = False) -> GitCommit:
        """
        Create a commit.

        Args:
            message: Commit message
            add_all: Stage all changes before committing

        Returns:
            The created GitCommit
        """
        if add_all:
            self.add(all=True)

        self._run_git("commit", "-m", message)

        # Get the commit we just made
        commits = self.log(count=1)
        return commits[0] if commits else None

    def amend(self, message: Optional[str] = None) -> GitCommit:
        """
        Amend the last commit.

        Args:
            message: New message (None = keep existing)

        Returns:
            The amended GitCommit
        """
        if message:
            self._run_git("commit", "--amend", "-m", message)
        else:
            self._run_git("commit", "--amend", "--no-edit")

        commits = self.log(count=1)
        return commits[0] if commits else None

    # =========================================================================
    # Branch Operations
    # =========================================================================

    def branches(self, all: bool = False) -> List[str]:
        """
        List branches.

        Args:
            all: Include remote branches

        Returns:
            List of branch names
        """
        args = ["branch"]
        if all:
            args.append("-a")

        _, stdout, _ = self._run_git(*args)

        branches = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            # Remove current branch marker and whitespace
            branch = line.replace("*", "").strip()
            branches.append(branch)

        return branches

    def current_branch(self) -> str:
        """Get the current branch name."""
        _, stdout, _ = self._run_git("branch", "--show-current")
        return stdout.strip() or "HEAD"

    def create_branch(self, name: str, checkout: bool = True) -> None:
        """
        Create a new branch.

        Args:
            name: Branch name
            checkout: Switch to the new branch
        """
        if checkout:
            self._run_git("checkout", "-b", name)
        else:
            self._run_git("branch", name)

    def checkout(self, branch: str) -> None:
        """
        Switch to a branch.

        Args:
            branch: Branch name or commit
        """
        self._run_git("checkout", branch)

    def delete_branch(self, name: str, force: bool = False) -> None:
        """
        Delete a branch.

        Args:
            name: Branch name
            force: Force delete (even if not merged)
        """
        flag = "-D" if force else "-d"
        self._run_git("branch", flag, name)

    # =========================================================================
    # Remote Operations
    # =========================================================================

    def fetch(self, remote: str = "origin") -> None:
        """Fetch from remote."""
        self._run_git("fetch", remote)

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> str:
        """
        Pull from remote.

        Args:
            remote: Remote name
            branch: Branch to pull (default: current)

        Returns:
            Pull output
        """
        args = ["pull", remote]
        if branch:
            args.append(branch)

        _, stdout, _ = self._run_git(*args)
        return stdout

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
    ) -> str:
        """
        Push to remote.

        Args:
            remote: Remote name
            branch: Branch to push (default: current)
            set_upstream: Set upstream tracking

        Returns:
            Push output
        """
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.append(remote)
        if branch:
            args.append(branch)

        _, stdout, stderr = self._run_git(*args)
        return stdout or stderr

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def stash(self, message: Optional[str] = None) -> None:
        """Stash changes."""
        if message:
            self._run_git("stash", "push", "-m", message)
        else:
            self._run_git("stash")

    def stash_pop(self) -> None:
        """Pop the last stash."""
        self._run_git("stash", "pop")

    def discard_changes(self, files: Optional[List[str]] = None) -> None:
        """
        Discard working tree changes.

        Args:
            files: Files to discard (None = all tracked files)
        """
        if files:
            self._run_git("checkout", "--", *files)
        else:
            self._run_git("checkout", "--", ".")

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the repository state.

        Returns:
            Summary string suitable for LLM context
        """
        status = self.status()
        commits = self.log(count=5)

        lines = [
            f"## Git Repository Status",
            f"",
            f"**Branch:** {status.branch}",
        ]

        if status.ahead:
            lines.append(f"**Ahead of origin:** {status.ahead} commit(s)")
        if status.behind:
            lines.append(f"**Behind origin:** {status.behind} commit(s)")

        if status.is_clean:
            lines.append(f"**Status:** Clean (no changes)")
        else:
            lines.append(f"")
            lines.append(f"**Changes:**")
            if status.staged:
                lines.append(f"- Staged: {len(status.staged)} file(s)")
                for f in status.staged[:5]:
                    lines.append(f"  - {f}")
            if status.modified:
                lines.append(f"- Modified: {len(status.modified)} file(s)")
                for f in status.modified[:5]:
                    lines.append(f"  - {f}")
            if status.untracked:
                lines.append(f"- Untracked: {len(status.untracked)} file(s)")
            if status.deleted:
                lines.append(f"- Deleted: {len(status.deleted)} file(s)")

        lines.extend([
            f"",
            f"**Recent commits:**",
        ])
        for c in commits[:5]:
            lines.append(f"- `{c.short_hash}` {c.message} ({c.author}, {c.date})")

        return "\n".join(lines)
