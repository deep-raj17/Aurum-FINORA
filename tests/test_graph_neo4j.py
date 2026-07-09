from datetime import UTC, datetime

import pytest

from aurum.knowledge_graph import (
    FinancialEntityExtractor,
    GraphEntity,
    GraphRelationship,
    Neo4jKnowledgeGraph,
    sample_contagion_graph,
)


class Result:
    def __init__(self, record=None) -> None:
        self.record = record

    def consume(self):
        return None

    def single(self):
        return self.record


class Session:
    def __init__(self, calls, record=None) -> None:
        self.calls = calls
        self.record = record

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return Result(self.record)


class Driver:
    def __init__(self, record=None) -> None:
        self.calls = []
        self.record = record

    def session(self, database):
        assert database == "neo4j"
        return Session(self.calls, self.record)

    def close(self):
        return None


def test_entity_extractor_normalizes_transformer_results() -> None:
    extractor = FinancialEntityExtractor(
        "finance-ner",
        pipeline=lambda text: [
            {"word": "Acme Corp", "entity_group": "ORG", "score": 0.99},
            {"word": "noise", "entity_group": "ORG", "score": 0.1},
        ],
    )
    entities = extractor.extract("Acme Corp reported results")
    assert [entity.entity_id for entity in entities] == ["company:acme corp"]


def test_neo4j_writes_parameterized_entities_and_allowlisted_edges() -> None:
    driver = Driver()
    graph = Neo4jKnowledgeGraph("bolt://unused", "neo4j", "secret", driver=driver)
    graph.initialize()
    graph.upsert_entities(
        [GraphEntity(entity_id="company:acme", name="Acme", entity_type="company")]
    )
    graph.upsert_relationships(
        [
            GraphRelationship(
                source_id="company:acme",
                target_id="sector:tech",
                relationship="OPERATES_IN",
                confidence=0.9,
                evidence_id="sec:1",
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ]
    )
    assert any("$rows" in query for query, _ in driver.calls)
    assert any("OPERATES_IN" in query for query, _ in driver.calls)
    assert all("company:acme" not in query for query, _ in driver.calls)


def test_neo4j_returns_explicit_path() -> None:
    record = {
        "names": ["Acme", "Technology"],
        "edges": [{"kind": "OPERATES_IN", "mechanism": "revenue exposure"}],
    }
    graph = Neo4jKnowledgeGraph("bolt://unused", "neo4j", "secret", driver=Driver(record))
    path = graph.path("company:acme", "sector:tech")
    assert path[0].mechanism == "revenue exposure"
    assert FinancialEntityExtractor("model", pipeline=lambda text: []).extract("") == []
    assert graph.upsert_entities([]) == 0
    assert graph.upsert_relationships([]) == 0
    with pytest.raises(ValueError, match="maximum_hops"):
        graph.path("a", "b", maximum_hops=20)


def test_sample_graph_covers_required_contagion_relationships() -> None:
    entities, relationships = sample_contagion_graph(datetime(2026, 1, 1, tzinfo=UTC))
    assert {
        "company",
        "sector",
        "country",
        "index",
        "currency",
        "macro",
        "news",
        "risk_factor",
        "shock",
    } <= {entity.entity_type for entity in entities}
    assert {"LISTED_IN", "DENOMINATED_IN", "AFFECTED_BY", "TRANSMITS_TO"} <= {
        relationship.relationship for relationship in relationships
    }
