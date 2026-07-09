"""Small in-memory hybrid retriever with temporal filtering.

Production adapters can replace this store with Qdrant/BM25 while preserving
the same evidence contract.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from hashlib import sha256

from pydantic import BaseModel, Field

from .models import Citation, Confidence

TOKEN = re.compile(r"[A-Za-z0-9_.$%-]+")


class Document(BaseModel):
    origin: str
    published_at: datetime
    text: str
    source_confidence: Confidence = Confidence.MEDIUM
    source_type: str = "unknown"
    entities: list[str] = Field(default_factory=list)


class InMemoryRetriever:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self.documents = list(documents or [])

    def add(self, document: Document) -> None:
        self.documents.append(document)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.lower() for token in TOKEN.findall(text)]

    @staticmethod
    def _dense_vector(tokens: list[str], dimensions: int = 128) -> dict[int, float]:
        vector: Counter[int] = Counter()
        for token in tokens:
            index = int.from_bytes(sha256(token.encode()).digest()[:4], "big") % dimensions
            vector[index] += 1
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        return {index: value / norm for index, value in vector.items()}

    @staticmethod
    def _cosine(left: dict[int, float], right: dict[int, float]) -> float:
        return sum(value * right.get(index, 0) for index, value in left.items())

    def search(self, query: str, *, as_of: datetime, limit: int = 5) -> list[Citation]:
        eligible = [doc for doc in self.documents if doc.published_at < as_of]
        if not eligible:
            return []
        query_counts = Counter(self._tokens(query))
        query_tokens = list(query_counts.elements())
        query_vector = self._dense_vector(query_tokens)
        query_bigrams = set(zip(query_tokens, query_tokens[1:], strict=False))
        document_counts = [Counter(self._tokens(doc.text)) for doc in eligible]
        document_frequency = Counter(token for counts in document_counts for token in counts)
        raw: list[tuple[float, float, float, Document]] = []
        for doc, counts in zip(eligible, document_counts, strict=True):
            lexical = 0.0
            for token, query_frequency in query_counts.items():
                inverse_frequency = (
                    math.log((len(eligible) + 1) / (document_frequency[token] + 1)) + 1
                )
                lexical += min(counts[token], query_frequency) * inverse_frequency
            length_penalty = math.sqrt(max(sum(counts.values()), 1))
            document_tokens = list(counts.elements())
            dense = self._cosine(query_vector, self._dense_vector(document_tokens))
            document_bigrams = set(zip(document_tokens, document_tokens[1:], strict=False))
            phrase = (
                len(query_bigrams & document_bigrams) / len(query_bigrams) if query_bigrams else 0.0
            )
            raw.append((lexical / length_penalty, dense, phrase, doc))
        max_lexical = max((item[0] for item in raw), default=1.0) or 1.0
        ranked = [
            (0.55 * lexical / max_lexical + 0.35 * dense + 0.10 * phrase, doc)
            for lexical, dense, phrase, doc in raw
            if lexical > 0 or dense > 0
        ]
        ranked.sort(key=lambda item: (item[0], item[1].published_at), reverse=True)
        max_score = ranked[0][0] if ranked else 1.0
        return [
            Citation(
                origin=doc.origin,
                published_at=doc.published_at,
                confidence=doc.source_confidence,
                relevance=min(score / max_score, 1.0),
                excerpt=doc.text[:500],
            )
            for score, doc in ranked[:limit]
        ]
