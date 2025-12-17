"""
Hybrid indexer combining keyword and semantic search.
"""

from typing import List, Tuple, Optional
from .indexer import CodebaseIndexer
from .semantic_indexer import SemanticIndexer, SemanticFileIndex


class HybridIndexer:
    """
    Combines keyword and semantic search with weighted scoring.

    Usage:
        indexer = HybridIndexer()
        indexer.index_directory("./project")
        results = indexer.search("user authentication", top_k=5)
    """

    def __init__(
        self,
        semantic_weight: float = 0.6,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """
        Args:
            semantic_weight: Weight for semantic scores (0-1). Keyword weight = 1 - semantic_weight
            model_name: sentence-transformers model for semantic search
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = 1.0 - semantic_weight

        self.keyword_indexer = CodebaseIndexer()
        self.semantic_indexer = SemanticIndexer(model_name=model_name)

        self.root_path: Optional[str] = None

    def index_directory(self, path: str, **kwargs) -> "HybridIndexer":
        """Index directory with both keyword and semantic indexers."""
        self.root_path = path
        self.keyword_indexer.index_directory(path, **kwargs)
        self.semantic_indexer.index_directory(path, **kwargs)
        return self

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Tuple[str, float, dict]]:
        """
        Hybrid search combining keyword and semantic results.

        Returns:
            List of (file_path, combined_score, {"keyword": score, "semantic": score})
        """
        # Get results from both indexers
        keyword_results = self.keyword_indexer.get_relevant_files(query, max_results=top_k * 2)
        semantic_results = self.semantic_indexer.search(query, top_k=top_k * 2)

        # Normalize keyword scores (they can vary widely)
        keyword_scores = {}
        if keyword_results:
            max_kw = max(r[1] for r in keyword_results) or 1.0
            for path, score, _ in keyword_results:
                keyword_scores[path] = score / max_kw

        # Collect semantic scores (already 0-1 range)
        semantic_scores = {}
        for path, score, _ in semantic_results:
            semantic_scores[path] = score

        # Merge all unique paths
        all_paths = set(keyword_scores.keys()) | set(semantic_scores.keys())

        # Calculate combined scores
        combined = []
        for path in all_paths:
            kw_score = keyword_scores.get(path, 0.0)
            sem_score = semantic_scores.get(path, 0.0)
            final_score = self.keyword_weight * kw_score + self.semantic_weight * sem_score
            combined.append((path, final_score, {"keyword": kw_score, "semantic": sem_score}))

        # Sort by combined score
        combined.sort(key=lambda x: -x[1])

        return combined[:top_k]

    def get_context_for_query(
        self,
        query: str,
        max_files: int = 3,
        max_lines: int = 150,
    ) -> str:
        """Get context string for LLM using hybrid search."""
        results = self.search(query, top_k=max_files)

        if not results:
            return f"No relevant files found in {self.root_path}"

        parts = [f"## Relevant files for: {query}\n"]

        for file_path, score, breakdown in results:
            parts.append(f"\n### {file_path}")
            parts.append(f"Score: {score:.3f} (kw: {breakdown['keyword']:.2f}, sem: {breakdown['semantic']:.2f})")

            # Get file content
            entry = self.semantic_indexer.index.get(file_path)
            if entry:
                try:
                    with open(entry.file_info.path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    if len(lines) > max_lines:
                        half = max_lines // 2
                        content = "".join(lines[:half])
                        content += f"\n... ({len(lines) - max_lines} lines omitted) ...\n"
                        content += "".join(lines[-half:])
                    else:
                        content = "".join(lines)

                    ext = entry.file_info.extension[1:] if entry.file_info.extension else ""
                    parts.append(f"```{ext}\n{content}\n```")
                except Exception as e:
                    parts.append(f"(Error: {e})")

        return "\n".join(parts)

    def get_project_overview(self) -> str:
        """Get project overview from keyword indexer."""
        return self.keyword_indexer.get_project_overview()

    def get_relevant_files(self, query: str, max_results: int = 10):
        """Get relevant files (for compatibility with CodebaseIndexer API)."""
        results = self.search(query, top_k=max_results)
        # Convert to CodebaseIndexer format: (path, score, FileIndex)
        return [
            (path, score, self.keyword_indexer.index.get(path))
            for path, score, _ in results
        ]

    @property
    def file_tree(self):
        """Access file tree from keyword indexer."""
        return self.keyword_indexer.file_tree
