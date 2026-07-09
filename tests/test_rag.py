from datetime import UTC, datetime, timedelta

from aurum.rag import (
    CrossEncoderReranker,
    ProductionRAG,
    QdrantHybridStore,
    RetrievalCandidate,
    SemanticChunker,
    SourceDocument,
)


class Store:
    def __init__(self) -> None:
        self.chunks = []

    def upsert(self, chunks) -> None:
        self.chunks.extend(chunks)

    def search(self, query, *, as_of, limit, metadata):
        return [
            RetrievalCandidate(chunk=chunk, score=0.5)
            for chunk in self.chunks
            if chunk.published_at < as_of
        ][:limit]


class KeywordReranker:
    def score(self, query, passages):
        return [float(passage.lower().count(query.lower())) for passage in passages]


def test_semantic_chunking_is_deterministic_and_overlapping() -> None:
    document = SourceDocument(
        document_id="filing",
        origin="SEC",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        text=" ".join(f"word{index}." for index in range(80)),
    )
    chunker = SemanticChunker(max_words=30, overlap_words=5)
    first = chunker.chunk(document)
    second = chunker.chunk(document)
    assert len(first) > 1
    assert first[0].chunk_id == second[0].chunk_id
    assert set(first[0].text.split()[-5:]) == set(first[1].text.split()[:5])


def test_production_rag_is_time_aware_reranked_and_attributed() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    rag = ProductionRAG(Store(), KeywordReranker(), chunker=SemanticChunker(30, 5))
    rag.index(
        [
            SourceDocument(
                document_id="old",
                origin="SEC filing",
                published_at=now - timedelta(days=1),
                text="Revenue rose. Revenue guidance improved.",
            ),
            SourceDocument(
                document_id="future",
                origin="Future filing",
                published_at=now + timedelta(days=1),
                text="Revenue collapsed.",
            ),
        ]
    )
    result = rag.search("revenue", as_of=now, limit=2)
    assert len(result) == 1
    assert result[0].origin.startswith("SEC filing#")
    assert result[0].published_at < now


def test_cross_encoder_validates_result_count() -> None:
    class Model:
        def predict(self, pairs):
            return [0.9 for _ in pairs]

    assert CrossEncoderReranker(model=Model()).score("query", ["one", "two"]) == [0.9, 0.9]


def test_qdrant_store_creates_indexes_upserts_and_hybrid_search(monkeypatch) -> None:
    class Value:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Models:
        VectorParams = SparseVectorParams = FieldCondition = Range = MatchValue = Value
        Prefetch = Document = FusionQuery = Filter = PointStruct = Value

        class Distance:
            COSINE = "cosine"

        class PayloadSchemaType:
            INTEGER = "integer"
            KEYWORD = "keyword"

        class Fusion:
            RRF = "rrf"

    monkeypatch.setattr(
        "aurum.rag.import_module",
        lambda name: Models if name == "qdrant_client.models" else None,
    )

    class Client:
        def __init__(self):
            self.exists = False
            self.points = []
            self.indexes = []

        def collection_exists(self, name):
            return self.exists

        def create_collection(self, **kwargs):
            self.exists = True

        def create_payload_index(self, **kwargs):
            self.indexes.append(kwargs["field_name"])

        def upsert(self, **kwargs):
            self.points = kwargs["points"]

        def query_points(self, **kwargs):
            point = self.points[0]
            return Value(points=[Value(payload=point.payload, score=0.8)])

    client = Client()
    store = QdrantHybridStore("http://qdrant", client=client)
    document = SourceDocument(
        document_id="doc",
        origin="SEC",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        text="Revenue increased.",
    )
    chunk = SemanticChunker().chunk(document)[0]
    store.upsert([chunk])
    result = store.search(
        "revenue",
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        limit=2,
        metadata={"source_type": "unknown"},
    )
    assert result[0].chunk.document_id == "doc"
    assert "published_at_epoch" in client.indexes
