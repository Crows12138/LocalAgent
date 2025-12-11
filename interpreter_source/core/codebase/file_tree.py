"""
File tree scanning and representation for codebase indexing.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


# Default patterns to ignore when scanning
DEFAULT_IGNORE_PATTERNS = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Dependencies
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # Build outputs
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "out",
    # IDE
    ".idea",
    ".vscode",
    ".vs",
    # OS
    ".DS_Store",
    "Thumbs.db",
    # Misc
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.exe",
    "*.log",
}

# File extensions we care about for code analysis
CODE_EXTENSIONS = {
    # Python
    ".py",
    ".pyi",
    ".pyw",
    # JavaScript/TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
    # Data/Config
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".ini",
    ".cfg",
    # Shell
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    # Other languages
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".swift",
    ".m",
    ".r",
    ".R",
    ".sql",
    ".lua",
    ".pl",
    ".pm",
    # Documentation
    ".md",
    ".rst",
    ".txt",
}


@dataclass
class FileInfo:
    """Information about a single file."""
    path: str
    relative_path: str
    extension: str
    size: int
    is_code: bool
    summary: Optional[str] = None

    def __post_init__(self):
        self.is_code = self.extension.lower() in CODE_EXTENSIONS


@dataclass
class FileTree:
    """
    Represents the file structure of a codebase.
    """
    root_path: str
    files: Dict[str, FileInfo] = field(default_factory=dict)
    directories: Set[str] = field(default_factory=set)
    ignore_patterns: Set[str] = field(default_factory=lambda: DEFAULT_IGNORE_PATTERNS.copy())

    def scan(self, max_file_size: int = 1_000_000) -> "FileTree":
        """
        Scan the directory and build the file tree.

        Args:
            max_file_size: Maximum file size in bytes to include (default 1MB)

        Returns:
            self for chaining
        """
        root = Path(self.root_path).resolve()

        if not root.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {self.root_path}")

        self.files.clear()
        self.directories.clear()

        for item in root.rglob("*"):
            # Check if any parent directory matches ignore patterns
            if self._should_ignore(item, root):
                continue

            relative = str(item.relative_to(root))

            if item.is_dir():
                self.directories.add(relative)
            elif item.is_file():
                try:
                    size = item.stat().st_size
                    if size <= max_file_size:
                        ext = item.suffix
                        self.files[relative] = FileInfo(
                            path=str(item),
                            relative_path=relative,
                            extension=ext,
                            size=size,
                            is_code=ext.lower() in CODE_EXTENSIONS,
                        )
                except (OSError, PermissionError):
                    # Skip files we can't access
                    pass

        return self

    def _should_ignore(self, path: Path, root: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        relative = path.relative_to(root)

        for part in relative.parts:
            if part in self.ignore_patterns:
                return True
            # Check glob patterns like *.pyc
            for pattern in self.ignore_patterns:
                if pattern.startswith("*") and part.endswith(pattern[1:]):
                    return True

        return False

    def get_code_files(self) -> List[FileInfo]:
        """Get all code files."""
        return [f for f in self.files.values() if f.is_code]

    def get_files_by_extension(self, ext: str) -> List[FileInfo]:
        """Get all files with a specific extension."""
        ext = ext if ext.startswith(".") else f".{ext}"
        return [f for f in self.files.values() if f.extension.lower() == ext.lower()]

    def get_tree_string(self, max_depth: int = 3) -> str:
        """
        Get a string representation of the file tree.

        Args:
            max_depth: Maximum depth to show

        Returns:
            Tree structure as string
        """
        lines = [f"{Path(self.root_path).name}/"]

        # Sort files and directories
        items = []
        for rel_path in sorted(self.files.keys()):
            depth = rel_path.count(os.sep)
            if depth < max_depth:
                items.append((rel_path, False))

        # Build tree
        for rel_path, is_dir in items:
            parts = rel_path.split(os.sep)
            depth = len(parts) - 1
            indent = "│   " * depth
            prefix = "├── " if depth > 0 else ""
            name = parts[-1]

            # Add file size for code files
            file_info = self.files.get(rel_path)
            if file_info and file_info.is_code:
                size_kb = file_info.size / 1024
                lines.append(f"{indent}{prefix}{name} ({size_kb:.1f}KB)")
            else:
                lines.append(f"{indent}{prefix}{name}")

        return "\n".join(lines[:100])  # Limit output

    def get_summary(self) -> Dict[str, any]:
        """Get a summary of the codebase."""
        code_files = self.get_code_files()

        # Count by extension
        ext_counts = {}
        for f in self.files.values():
            ext = f.extension.lower() or "(no extension)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        # Sort by count
        sorted_exts = sorted(ext_counts.items(), key=lambda x: -x[1])

        return {
            "total_files": len(self.files),
            "code_files": len(code_files),
            "total_directories": len(self.directories),
            "total_size_bytes": sum(f.size for f in self.files.values()),
            "extensions": dict(sorted_exts[:10]),  # Top 10
        }
