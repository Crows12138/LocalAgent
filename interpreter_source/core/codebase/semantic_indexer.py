"""
Semantic codebase indexer using embedding models.

Enables semantic search - finding relevant code by meaning rather than keywords.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .file_tree import FileTree, FileInfo


@dataclass
class SemanticFileIndex:
    """Index entry with embedding vector."""
    file_info: FileInfo
    summary: str = ""
    content_preview: str = ""
    embedding: Optional[np.ndarray] = None


class SemanticIndexer:
    """
    Semantic code search using sentence embeddings.

    Usage:
        indexer = SemanticIndexer()
        indexer.index_directory("./project")
        results = indexer.search("user authentication", top_k=5)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Args:
            model_name: sentence-transformers model
                - "all-MiniLM-L6-v2": fast, 384-dim
                - "paraphrase-multilingual-MiniLM-L12-v2": multilingual
        """
        self.model_name = model_name
        self.model = None
        self.file_tree: Optional[FileTree] = None
        self.index: Dict[str, SemanticFileIndex] = {}
        self.root_path: Optional[str] = None
        self._embedding_matrix: Optional[np.ndarray] = None
        self._file_paths: List[str] = [] 

    def _load_model(self):
        """Lazy load embedding model."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Convert text to embedding vector."""
        self._load_model()
        if len(text) > 8000:
            text = text[:4000] + "\n...\n" + text[-4000:]
        return self.model.encode(text, convert_to_numpy=True)

    def index_directory(
        self,
        path: str,
        max_file_size: int = 100_000,
        preview_chars: int = 2000,
    ) -> "SemanticIndexer":
        """Index a directory with semantic embeddings."""
        self.root_path = str(Path(path).resolve())
        self.file_tree = FileTree(self.root_path)
        self.file_tree.scan(max_file_size=max_file_size)
        self.index.clear()

        code_files = [
            (rel_path, file_info)
            for rel_path, file_info in self.file_tree.files.items()
            if file_info.is_code
        ]

        embeddings = []
        self._file_paths = []

        for rel_path, file_info in code_files:
            entry = self._index_file(file_info, preview_chars)
            if entry.embedding is not None:
                self.index[rel_path] = entry
                embeddings.append(entry.embedding)
                self._file_paths.append(rel_path)

        if embeddings:
            self._embedding_matrix = np.vstack(embeddings)

        return self

    def _index_file(self, file_info: FileInfo, preview_chars: int) -> SemanticFileIndex:
        """Index a single file."""
        entry = SemanticFileIndex(file_info=file_info)

        try:
            with open(file_info.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return entry

        filename = Path(file_info.path).name
        rel_path = str(Path(file_info.path).relative_to(self.root_path))

        entry.summary = f"File: {filename} | Path: {rel_path}"
        entry.content_preview = content[:preview_chars]

        embed_text = entry.summary + "\n" + entry.content_preview
        entry.embedding = self._get_embedding(embed_text)

        return entry

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Tuple[str, float, SemanticFileIndex]]:
        """
        Semantic search for relevant files.

        Args:
            query: Natural language query
            top_k: Number of results

        Returns:
            List of (file_path, similarity_score, index_entry)
        """
        if self._embedding_matrix is None or len(self._file_paths) == 0:
            return []

        query_embedding = self._get_embedding(query)

        # Cosine similarity: dot(q, d) / (||q|| * ||d||)
        query_norm = np.linalg.norm(query_embedding)
        doc_norms = np.linalg.norm(self._embedding_matrix, axis=1)

        dot_products = self._embedding_matrix @ query_embedding
        similarities = dot_products / (doc_norms * query_norm + 1e-8)

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            file_path = self._file_paths[idx]
            score = float(similarities[idx])
            entry = self.index[file_path]
            results.append((file_path, score, entry))

        return results

    def get_context_for_query(
        self,
        query: str,
        max_files: int = 3,
        max_lines: int = 150,
    ) -> str:
        """Get context string for LLM prompt."""
        results = self.search(query, top_k=max_files)

        if not results:
            return f"No relevant files found in {self.root_path}"

        parts = [f"## Relevant files for: {query}\n"]

        for file_path, score, entry in results:
            parts.append(f"\n### {file_path} (score: {score:.3f})")

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
                parts.append(f"(Error reading file: {e})")

        return "\n".join(parts)
