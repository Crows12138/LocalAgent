"""
Codebase indexing and understanding module for LocalAgent.

This module provides functionality to:
1. Scan and index project file structures
2. Generate summaries of code files
3. Retrieve relevant files based on user queries
"""

from .indexer import CodebaseIndexer
from .file_tree import FileTree

__all__ = ["CodebaseIndexer", "FileTree"]
