"""
Codebase indexer for LocalAgent.

Provides intelligent code understanding by:
1. Scanning project structure
2. Generating file summaries
3. Building a searchable index
4. Retrieving relevant context for queries
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .file_tree import FileTree, FileInfo


@dataclass
class FileIndex:
    """Index entry for a single file."""
    file_info: FileInfo
    summary: str = ""
    symbols: List[str] = field(default_factory=list)  # Functions, classes, etc.
    imports: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


class CodebaseIndexer:
    """
    Indexes a codebase for intelligent context retrieval.

    Usage:
        indexer = CodebaseIndexer()
        indexer.index_directory("./my_project")

        # Get relevant files for a query
        relevant = indexer.get_relevant_files("user authentication")

        # Get context string for LLM
        context = indexer.get_context_for_query("fix login bug", max_files=5)
    """

    def __init__(self):
        self.file_tree: Optional[FileTree] = None
        self.index: Dict[str, FileIndex] = {}
        self.root_path: Optional[str] = None

    def index_directory(
        self,
        path: str,
        max_file_size: int = 500_000,  # 500KB
        summarize: bool = True,
    ) -> "CodebaseIndexer":
        """
        Index a directory.

        Args:
            path: Path to the directory
            max_file_size: Maximum file size to index
            summarize: Whether to generate summaries (requires reading files)

        Returns:
            self for chaining
        """
        self.root_path = str(Path(path).resolve())
        self.file_tree = FileTree(self.root_path)
        self.file_tree.scan(max_file_size=max_file_size)
        self.index.clear()

        # Index each code file
        for rel_path, file_info in self.file_tree.files.items():
            if file_info.is_code:
                entry = self._index_file(file_info, summarize)
                self.index[rel_path] = entry

        return self

    def _index_file(self, file_info: FileInfo, summarize: bool) -> FileIndex:
        """Index a single file."""
        entry = FileIndex(file_info=file_info)

        try:
            with open(file_info.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return entry

        # Extract based on file type
        ext = file_info.extension.lower()

        if ext in (".py", ".pyi"):
            entry.symbols = self._extract_python_symbols(content)
            entry.imports = self._extract_python_imports(content)
        elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
            entry.symbols = self._extract_js_symbols(content)
            entry.imports = self._extract_js_imports(content)
        elif ext in (".java", ".kt", ".scala"):
            entry.symbols = self._extract_java_symbols(content)
        elif ext in (".go",):
            entry.symbols = self._extract_go_symbols(content)
        elif ext in (".rs",):
            entry.symbols = self._extract_rust_symbols(content)

        # Extract keywords from content
        entry.keywords = self._extract_keywords(content)

        # Generate summary
        if summarize:
            entry.summary = self._generate_summary(file_info, entry, content)

        return entry

    def _extract_python_symbols(self, content: str) -> List[str]:
        """Extract Python function and class names."""
        symbols = []
        # Classes
        for match in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
            symbols.append(f"class:{match.group(1)}")
        # Functions
        for match in re.finditer(r"^(?:async\s+)?def\s+(\w+)", content, re.MULTILINE):
            symbols.append(f"def:{match.group(1)}")
        return symbols

    def _extract_python_imports(self, content: str) -> List[str]:
        """Extract Python imports."""
        imports = []
        for match in re.finditer(r"^(?:from\s+(\S+)\s+)?import\s+(.+)$", content, re.MULTILINE):
            if match.group(1):
                imports.append(match.group(1))
            else:
                imports.extend(match.group(2).split(","))
        return [i.strip().split()[0] for i in imports if i.strip()]

    def _extract_js_symbols(self, content: str) -> List[str]:
        """Extract JavaScript/TypeScript symbols."""
        symbols = []
        # Functions
        for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", content):
            symbols.append(f"function:{match.group(1)}")
        # Arrow functions assigned to const
        for match in re.finditer(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(", content):
            symbols.append(f"const:{match.group(1)}")
        # Classes
        for match in re.finditer(r"(?:export\s+)?class\s+(\w+)", content):
            symbols.append(f"class:{match.group(1)}")
        return symbols

    def _extract_js_imports(self, content: str) -> List[str]:
        """Extract JS imports."""
        imports = []
        for match in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", content):
            imports.append(match.group(1))
        return imports

    def _extract_java_symbols(self, content: str) -> List[str]:
        """Extract Java/Kotlin symbols."""
        symbols = []
        for match in re.finditer(r"(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum)\s+(\w+)", content):
            symbols.append(f"class:{match.group(1)}")
        for match in re.finditer(r"(?:public|private|protected)\s+(?:static\s+)?[\w<>,\s]+\s+(\w+)\s*\(", content):
            symbols.append(f"method:{match.group(1)}")
        return symbols

    def _extract_go_symbols(self, content: str) -> List[str]:
        """Extract Go symbols."""
        symbols = []
        for match in re.finditer(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", content, re.MULTILINE):
            symbols.append(f"func:{match.group(1)}")
        for match in re.finditer(r"^type\s+(\w+)\s+struct", content, re.MULTILINE):
            symbols.append(f"struct:{match.group(1)}")
        return symbols

    def _extract_rust_symbols(self, content: str) -> List[str]:
        """Extract Rust symbols."""
        symbols = []
        for match in re.finditer(r"^(?:pub\s+)?fn\s+(\w+)", content, re.MULTILINE):
            symbols.append(f"fn:{match.group(1)}")
        for match in re.finditer(r"^(?:pub\s+)?struct\s+(\w+)", content, re.MULTILINE):
            symbols.append(f"struct:{match.group(1)}")
        for match in re.finditer(r"^(?:pub\s+)?impl\s+(\w+)", content, re.MULTILINE):
            symbols.append(f"impl:{match.group(1)}")
        return symbols

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract significant keywords from content."""
        # Remove comments and strings (simplified)
        clean = re.sub(r'["\'].*?["\']', "", content)
        clean = re.sub(r"#.*$", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"//.*$", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)

        # Extract words
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", clean)

        # Count frequency
        freq = {}
        for w in words:
            w_lower = w.lower()
            freq[w_lower] = freq.get(w_lower, 0) + 1

        # Filter common programming keywords
        common = {"def", "class", "function", "return", "import", "from", "if", "else",
                  "for", "while", "try", "except", "with", "as", "in", "is", "not",
                  "and", "or", "true", "false", "none", "null", "self", "this",
                  "var", "let", "const", "async", "await", "export", "default"}

        keywords = [w for w, c in freq.items() if c >= 2 and w not in common]
        return sorted(keywords, key=lambda x: -freq[x])[:20]

    def _generate_summary(self, file_info: FileInfo, entry: FileIndex, content: str) -> str:
        """Generate a brief summary of the file."""
        parts = []

        # File type
        ext = file_info.extension.lower()
        if ext == ".py":
            parts.append("Python module")
        elif ext in (".js", ".jsx"):
            parts.append("JavaScript file")
        elif ext in (".ts", ".tsx"):
            parts.append("TypeScript file")
        elif ext == ".java":
            parts.append("Java class")
        elif ext == ".go":
            parts.append("Go source")
        elif ext == ".rs":
            parts.append("Rust source")
        else:
            parts.append(f"{ext} file")

        # Count symbols
        classes = [s for s in entry.symbols if s.startswith("class:")]
        functions = [s for s in entry.symbols if any(s.startswith(p) for p in ("def:", "function:", "fn:", "func:", "method:"))]

        if classes:
            parts.append(f"{len(classes)} class(es): {', '.join(s.split(':')[1] for s in classes[:3])}")
        if functions:
            parts.append(f"{len(functions)} function(s)")

        # Line count
        lines = content.count("\n") + 1
        parts.append(f"{lines} lines")

        return " | ".join(parts)

    def get_relevant_files(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[Tuple[str, float, FileIndex]]:
        """
        Get files relevant to a query.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of (relative_path, score, FileIndex) tuples
        """
        if not self.index:
            return []

        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        results = []

        for rel_path, entry in self.index.items():
            score = self._calculate_relevance(query_words, rel_path, entry)
            if score > 0:
                results.append((rel_path, score, entry))

        # Sort by score descending
        results.sort(key=lambda x: -x[1])
        return results[:max_results]

    def _calculate_relevance(
        self,
        query_words: set,
        rel_path: str,
        entry: FileIndex,
    ) -> float:
        """Calculate relevance score for a file."""
        score = 0.0

        # Check filename
        filename = Path(rel_path).name.lower()
        for word in query_words:
            if word in filename:
                score += 3.0

        # Check path
        path_lower = rel_path.lower()
        for word in query_words:
            if word in path_lower:
                score += 1.0

        # Check symbols
        symbols_str = " ".join(entry.symbols).lower()
        for word in query_words:
            if word in symbols_str:
                score += 2.0

        # Check keywords
        keywords_str = " ".join(entry.keywords)
        for word in query_words:
            if word in keywords_str:
                score += 1.0

        # Check summary
        if entry.summary and any(w in entry.summary.lower() for w in query_words):
            score += 0.5

        return score

    def get_context_for_query(
        self,
        query: str,
        max_files: int = 5,
        max_content_per_file: int = 200,  # lines
    ) -> str:
        """
        Get context string for an LLM query.

        Args:
            query: User's query
            max_files: Maximum number of files to include
            max_content_per_file: Maximum lines per file

        Returns:
            Context string with relevant file contents
        """
        relevant = self.get_relevant_files(query, max_results=max_files)

        if not relevant:
            return f"No relevant files found in {self.root_path}"

        parts = [f"## Relevant files for: {query}\n"]

        for rel_path, score, entry in relevant:
            parts.append(f"\n### {rel_path}")
            parts.append(f"Summary: {entry.summary}")

            # Read file content
            try:
                with open(entry.file_info.path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                if len(lines) > max_content_per_file:
                    # Show first and last parts
                    half = max_content_per_file // 2
                    content = "".join(lines[:half])
                    content += f"\n... ({len(lines) - max_content_per_file} lines omitted) ...\n"
                    content += "".join(lines[-half:])
                else:
                    content = "".join(lines)

                ext = entry.file_info.extension[1:] if entry.file_info.extension else ""
                parts.append(f"```{ext}\n{content}\n```")

            except Exception as e:
                parts.append(f"(Could not read file: {e})")

        return "\n".join(parts)

    def get_project_overview(self) -> str:
        """Get an overview of the project structure."""
        if not self.file_tree:
            return "No project indexed"

        summary = self.file_tree.get_summary()
        tree_str = self.file_tree.get_tree_string(max_depth=2)

        overview = [
            f"## Project: {Path(self.root_path).name}",
            f"",
            f"**Statistics:**",
            f"- Total files: {summary['total_files']}",
            f"- Code files: {summary['code_files']}",
            f"- Directories: {summary['total_directories']}",
            f"- Total size: {summary['total_size_bytes'] / 1024 / 1024:.1f} MB",
            f"",
            f"**File types:**",
        ]

        for ext, count in list(summary['extensions'].items())[:5]:
            overview.append(f"- {ext}: {count} files")

        overview.extend([
            f"",
            f"**Structure:**",
            f"```",
            tree_str,
            f"```",
        ])

        return "\n".join(overview)
