"""
BM25 lexical index with financial token preservation and artifact persistence.
"""

import pickle
import re
from pathlib import Path
from typing import List, Optional, Tuple
from rank_bm25 import BM25Plus

from veridocs.schemas.data_models import ChunkRecord
from veridocs.sec.provenance import compute_sha256

# Regex for financial tokens:
# Matches:
# - ($1.2B) or (1,245) or ($500M)
# - +5.2% or -3.8% or 12.5%
# - $383,285 or 123,400.50
# - FY2023 or Q3 or 2024
# - Item 1A or Item 8
# - Alphanumeric words & identifiers
FINANCIAL_TOKEN_PATTERN = re.compile(
    r"""
    (?:\([$€£¥]?\d+(?:,\d+)*(?:\.\d+)?[BMKbmk%]?\)) |   # Parenthetical negatives e.g. ($1.2B), (1,245)
    (?:[+-]?\d+(?:,\d+)*(?:\.\d+)?%)               |   # Percentages e.g. +5.2%, -3.8%
    (?:[$€£¥]\d+(?:,\d+)*(?:\.\d+)?)               |   # Currencies e.g. $383,285
    (?:(?:FY|Q[1-4]|Item)\s*\d+[A-Za-z]?)          |   # FY2023, Q3, Item 1A
    (?:\b\d+(?:,\d+)*(?:\.\d+)?\b)                 |   # Regular numbers with commas / decimals
    (?:\b[A-Za-z0-9_\-']+\b)                            # Standard words & tickers
    """,
    re.VERBOSE | re.IGNORECASE,
)


def tokenize_financial_text(text: str) -> List[str]:
    """
    Deterministic tokenizer that preserves financial symbols, signs, decimals,
    periods, and accounting parenthetical negatives while lowercasing words.
    """
    if not text:
        return []
    matches = FINANCIAL_TOKEN_PATTERN.findall(text)
    # Lowercase standard words, but preserve case-insensitive financial tokens
    tokens = [m.lower().replace(" ", "") for m in matches if m.strip()]
    return tokens


class BM25Index:
    """
    Lexical BM25 index built from persisted chunk records using BM25Plus
    to prevent zero/negative scoring on small corpora or high-frequency terms.
    """

    def __init__(self, chunk_ids: List[str], bm25: BM25Plus, corpus_tokens: List[List[str]]):
        self.chunk_ids = chunk_ids
        self.bm25 = bm25
        self.corpus_tokens = corpus_tokens

    @classmethod
    def build(cls, chunks: List[ChunkRecord]) -> "BM25Index":
        chunk_ids = [c.chunk_id for c in chunks]
        corpus_tokens = [tokenize_financial_text(c.text) for c in chunks]
        # Handle empty corpus defensively
        if not corpus_tokens or all(len(t) == 0 for t in corpus_tokens):
            corpus_tokens = [["empty"]]
            chunk_ids = ["dummy_empty"]
        bm25 = BM25Plus(corpus_tokens)
        return cls(chunk_ids=chunk_ids, bm25=bm25, corpus_tokens=corpus_tokens)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Scores query against BM25 index, returning sorted list of (chunk_id, score).
        """
        query_tokens = tokenize_financial_text(query)
        if not query_tokens or not self.chunk_ids:
            return []

        scores = self.bm25.get_scores(query_tokens)
        scored_pairs = list(zip(self.chunk_ids, scores))
        # Sort descending by score; break ties deterministically by chunk_id
        scored_pairs.sort(key=lambda x: (x[1], x[0]), reverse=True)
        # Filter strictly positive scores
        positive_pairs = [(cid, float(score)) for cid, score in scored_pairs if score > 0.0]
        return positive_pairs[:top_k]

    def save(self, artifact_path: Path) -> str:
        """Saves BM25 index artifact and returns its SHA-256 checksum."""
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunk_ids": self.chunk_ids,
            "corpus_tokens": self.corpus_tokens,
        }
        data = pickle.dumps(payload)
        with open(artifact_path, "wb") as f:
            f.write(data)
        return compute_sha256(data)

    @classmethod
    def load(cls, artifact_path: Path) -> "BM25Index":
        """Loads BM25 index from disk."""
        with open(artifact_path, "rb") as f:
            payload = pickle.load(f)
        chunk_ids = payload["chunk_ids"]
        corpus_tokens = payload["corpus_tokens"]
        bm25 = BM25Plus(corpus_tokens)
        return cls(chunk_ids=chunk_ids, bm25=bm25, corpus_tokens=corpus_tokens)
