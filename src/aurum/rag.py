"""Production retrieval: chunking, Qdrant hybrid search, reranking, and attribution."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field

from .models import Citation, Confidence

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


class SourceDocument(BaseModel):
    document_id: str = Field(min_length=1)
    origin: str
    published_at: datetime
    text: str = Field(min_length=1)
    source_confidence: Confidence = Confidence.MEDIUM
    source_type: str = "unknown"
    entities: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    origin: str
    published_at: datetime
    text: str
    sequence: int = Field(ge=0)
    source_confidence: Confidence
    source_type: str
    entities: list[str]
    metadata: dict[str, str | int | float | bool]
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SemanticChunker:
    """Sentence-preserving, token-bounded chunks with deterministic overlap."""

    def __init__(self, max_words: int = 300, overlap_words: int = 50) -> None:
        if max_words < 20 or not 0 <= overlap_words < max_words:
            raise ValueError("chunk sizes require max_words >= 20 and overlap < max_words")
        self.max_words = max_words
        self.overlap_words = overlap_words

    def chunk(self, document: SourceDocument) -> list[DocumentChunk]:
        sentences = [
            sentence.strip()
            for sentence in SENTENCE_BOUNDARY.split(document.text)
            if sentence.strip()
        ]
        chunks: list[str] = []
        current: list[str] = []
        count = 0
        for sentence in sentences:
            words = sentence.split()
            if current and count + len(words) > self.max_words:
                chunks.append(" ".join(current))
                overlap = " ".join(current).split()[-self.overlap_words :]
                current = [" ".join(overlap)] if overlap else []
                count = len(overlap)
            while len(words) > self.max_words:
                capacity = max(self.max_words - count, 1)
                current.append(" ".join(words[:capacity]))
                chunks.append(" ".join(current))
                overlap = chunks[-1].split()[-self.overlap_words :]
                current = [" ".join(overlap)] if overlap else []
                count = len(overlap)
                words = words[capacity:]
            if words:
                current.append(" ".join(words))
                count += len(words)
        if current:
            chunks.append(" ".join(current))
        result = []
        for sequence, text in enumerate(chunks):
            content_hash = sha256(text.encode()).hexdigest()
            chunk_id = sha256(
                f"{document.document_id}:{sequence}:{content_hash}".encode()
            ).hexdigest()
            result.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    origin=document.origin,
                    published_at=document.published_at.astimezone(UTC),
                    text=text,
                    sequence=sequence,
                    source_confidence=document.source_confidence,
                    source_type=document.source_type,
                    entities=document.entities,
                    metadata=document.metadata,
                    content_sha256=content_hash,
                )
            )
        return result


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk: DocumentChunk
    score: float


class HybridStore(Protocol):
    def upsert(self, chunks: Sequence[DocumentChunk]) -> None: ...

    def search(
        self,
        query: str,
        *,
        as_of: datetime,
        limit: int,
        metadata: dict[str, str | int | float | bool] | None,
    ) -> list[RetrievalCandidate]: ...


class Reranker(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(
        self,
        model_id: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
        *,
        model: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self._model = model

    def _load(self) -> Any:
        if self._model is None:
            self._model = import_module("sentence_transformers").CrossEncoder(self.model_id)
        return self._model

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        values = self._load().predict([(query, passage) for passage in passages])
        scores = [float(value) for value in values]
        if len(scores) != len(passages):
            raise RuntimeError("cross-encoder returned an unexpected number of scores")
        return scores


class QdrantHybridStore:
    """Qdrant dense + BM25 retrieval fused with reciprocal rank fusion."""

    def __init__(
        self,
        url: str,
        *,
        collection: str = "finora_evidence",
        api_key: str | None = None,
        dense_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        sparse_model: str = "Qdrant/bm25",
        dense_size: int = 384,
        client: Any | None = None,
    ) -> None:
        self.collection = collection
        self.dense_model = dense_model
        self.sparse_model = sparse_model
        self.dense_size = dense_size
        if client is None:
            client_type = import_module("qdrant_client").QdrantClient
            client = client_type(url=url, api_key=api_key, timeout=30)
        self.client = client

    def ensure_collection(self) -> None:
        models = import_module("qdrant_client.models")
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": models.VectorParams(size=self.dense_size, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )
        for field in ("published_at_epoch", "source_type", "document_id", "entities"):
            schema = (
                models.PayloadSchemaType.INTEGER
                if field == "published_at_epoch"
                else models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.collection, field_name=field, field_schema=schema
            )

    def upsert(self, chunks: Sequence[DocumentChunk]) -> None:
        if not chunks:
            return
        self.ensure_collection()
        models = import_module("qdrant_client.models")
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector={
                    "dense": models.Document(text=chunk.text, model=self.dense_model),
                    "sparse": models.Document(text=chunk.text, model=self.sparse_model),
                },
                payload={
                    **chunk.model_dump(mode="json"),
                    "published_at_epoch": int(chunk.published_at.timestamp()),
                },
            )
            for chunk in chunks
        ]
        self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def search(
        self,
        query: str,
        *,
        as_of: datetime,
        limit: int,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> list[RetrievalCandidate]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        models = import_module("qdrant_client.models")
        must = [
            models.FieldCondition(
                key="published_at_epoch",
                range=models.Range(lt=int(as_of.timestamp())),
            )
        ]
        for key, value in (metadata or {}).items():
            if key not in {"source_type", "document_id", "entities"}:
                raise ValueError(f"metadata filter is not indexed: {key}")
            must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
        response = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=models.Document(text=query, model=self.dense_model),
                    using="dense",
                    limit=max(limit * 4, 20),
                ),
                models.Prefetch(
                    query=models.Document(text=query, model=self.sparse_model),
                    using="sparse",
                    limit=max(limit * 4, 20),
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=models.Filter(must=must),
            with_payload=True,
            limit=limit,
        )
        candidates = []
        for point in response.points:
            if not point.payload:
                raise RuntimeError("Qdrant result omitted the evidence payload")
            payload = dict(point.payload)
            payload.pop("published_at_epoch", None)
            candidates.append(
                RetrievalCandidate(
                    chunk=DocumentChunk.model_validate(payload),
                    score=float(point.score),
                )
            )
        return candidates


class ProductionRAG:
    """Indexes sources and returns reranked citations with time-aware attribution."""

    def __init__(
        self,
        store: HybridStore,
        reranker: Reranker,
        *,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self.store = store
        self.reranker = reranker
        self.chunker = chunker or SemanticChunker()

    def index(self, documents: Sequence[SourceDocument]) -> int:
        chunks = [chunk for document in documents for chunk in self.chunker.chunk(document)]
        self.store.upsert(chunks)
        return len(chunks)

    def search(
        self,
        query: str,
        *,
        as_of: datetime,
        limit: int = 5,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> list[Citation]:
        if not query.strip() or limit < 1:
            raise ValueError("query must be non-empty and limit must be positive")
        candidates = self.store.search(
            query, as_of=as_of, limit=max(limit * 4, 20), metadata=metadata
        )
        if not candidates:
            return []
        rerank_scores = self.reranker.score(
            query, [candidate.chunk.text for candidate in candidates]
        )
        ranked = sorted(
            zip(candidates, rerank_scores, strict=True),
            key=lambda item: (item[1], item[0].score, item[0].chunk.published_at),
            reverse=True,
        )
        maximum = max((score for _, score in ranked), default=1.0)
        minimum = min((score for _, score in ranked), default=0.0)
        span = maximum - minimum or 1.0
        return [
            Citation(
                origin=f"{candidate.chunk.origin}#{candidate.chunk.chunk_id[:12]}",
                published_at=candidate.chunk.published_at,
                confidence=candidate.chunk.source_confidence,
                relevance=max(0.0, min(1.0, (score - minimum) / span)),
                excerpt=candidate.chunk.text[:500],
            )
            for candidate, score in ranked[:limit]
        ]
