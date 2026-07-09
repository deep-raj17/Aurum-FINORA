"""Neo4j financial knowledge graph and transformer entity extraction."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import import_module
from typing import Any, Literal

from pydantic import BaseModel, Field

from .graph import Edge

EntityType = Literal[
    "company",
    "sector",
    "country",
    "index",
    "currency",
    "asset",
    "macro",
    "news",
    "risk_factor",
    "shock",
    "owner",
    "supplier",
    "unknown",
]
RelationshipType = Literal[
    "OPERATES_IN",
    "OWNS",
    "SUPPLIES",
    "MENTIONED_IN",
    "EXPOSED_TO",
    "COMPETES_WITH",
    "SUBSIDIARY_OF",
    "LISTED_IN",
    "DENOMINATED_IN",
    "LOCATED_IN",
    "TRACKED_BY",
    "AFFECTED_BY",
    "TRANSMITS_TO",
]


class GraphEntity(BaseModel):
    entity_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=500)
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    relationship: RelationshipType
    confidence: float = Field(ge=0, le=1)
    evidence_id: str
    observed_at: datetime
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)


def sample_contagion_graph(
    observed_at: datetime,
) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """Small, provenance-labelled graph used for Neo4j ingestion validation."""
    entities = [
        GraphEntity(entity_id="company:acme", name="Acme", entity_type="company"),
        GraphEntity(entity_id="sector:technology", name="Technology", entity_type="sector"),
        GraphEntity(entity_id="country:us", name="United States", entity_type="country"),
        GraphEntity(entity_id="index:sp500", name="S&P 500", entity_type="index"),
        GraphEntity(entity_id="currency:usd", name="US Dollar", entity_type="currency"),
        GraphEntity(entity_id="macro:rates", name="Policy Rates", entity_type="macro"),
        GraphEntity(entity_id="news:sample", name="Sample News Event", entity_type="news"),
        GraphEntity(entity_id="risk:funding", name="Funding Risk", entity_type="risk_factor"),
        GraphEntity(entity_id="shock:rates", name="Rate Shock", entity_type="shock"),
    ]
    relations: list[tuple[str, str, RelationshipType]] = [
        ("company:acme", "sector:technology", "OPERATES_IN"),
        ("sector:technology", "country:us", "LOCATED_IN"),
        ("company:acme", "index:sp500", "LISTED_IN"),
        ("company:acme", "currency:usd", "DENOMINATED_IN"),
        ("company:acme", "macro:rates", "EXPOSED_TO"),
        ("company:acme", "news:sample", "MENTIONED_IN"),
        ("company:acme", "risk:funding", "AFFECTED_BY"),
        ("shock:rates", "risk:funding", "TRANSMITS_TO"),
    ]
    relationships = [
        GraphRelationship(
            source_id=source,
            target_id=target,
            relationship=relationship,
            confidence=1.0,
            evidence_id="sample:phase3a",
            observed_at=observed_at,
            properties={"sample": True, "mechanism": "research validation"},
        )
        for source, target, relationship in relations
    ]
    return entities, relationships


class FinancialEntityExtractor:
    """Transformer NER adapter that emits normalized, provenance-ready entities."""

    LABELS: dict[str, EntityType] = {
        "ORG": "company",
        "COMPANY": "company",
        "SECTOR": "sector",
        "INDUSTRY": "sector",
        "OWNER": "owner",
        "PERSON": "owner",
        "SUPPLIER": "supplier",
        "ECONOMIC_INDICATOR": "macro",
        "MACRO": "macro",
        "EVENT": "news",
    }

    def __init__(
        self,
        model_id: str,
        *,
        pipeline: Any | None = None,
        confidence_threshold: float = 0.75,
    ) -> None:
        self.model_id = model_id
        self._pipeline = pipeline
        self.confidence_threshold = confidence_threshold

    def _load(self) -> Any:
        if self._pipeline is None:
            pipeline_factory = import_module("transformers").pipeline
            self._pipeline = pipeline_factory(
                "token-classification",
                model=self.model_id,
                aggregation_strategy="simple",
            )
        return self._pipeline

    def extract(self, text: str) -> list[GraphEntity]:
        if not text.strip():
            return []
        raw = self._load()(text)
        entities: dict[str, GraphEntity] = {}
        for item in raw:
            score = float(item.get("score", 0))
            name = str(item.get("word", "")).strip()
            label = str(item.get("entity_group", item.get("entity", ""))).upper()
            if not name or score < self.confidence_threshold:
                continue
            entity_type = self.LABELS.get(label, "unknown")
            entity_id = f"{entity_type}:{' '.join(name.lower().split())}"
            entities[entity_id] = GraphEntity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                properties={"extraction_confidence": score, "model_id": self.model_id},
            )
        return list(entities.values())


class Neo4jKnowledgeGraph:
    """Parameterized Neo4j persistence with idempotent nodes and evidence edges."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        *,
        database: str = "neo4j",
        driver: Any | None = None,
    ) -> None:
        if driver is None:
            graph_database = import_module("neo4j").GraphDatabase
            driver = graph_database.driver(uri, auth=(username, password))
        self.driver = driver
        self.database = database

    def close(self) -> None:
        self.driver.close()

    def initialize(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                "CREATE CONSTRAINT finora_entity_id IF NOT EXISTS "
                "FOR (entity:Entity) REQUIRE entity.entity_id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE INDEX finora_entity_type IF NOT EXISTS "
                "FOR (entity:Entity) ON (entity.entity_type)"
            ).consume()

    def upsert_entities(self, entities: Sequence[GraphEntity]) -> int:
        if not entities:
            return 0
        rows = [
            {
                **entity.model_dump(exclude={"properties"}),
                "properties": entity.properties,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            for entity in entities
        ]
        query = """
        UNWIND $rows AS row
        MERGE (entity:Entity {entity_id: row.entity_id})
        SET entity.name = row.name,
            entity.entity_type = row.entity_type,
            entity.aliases = row.aliases,
            entity.updated_at = datetime(row.updated_at)
        SET entity += row.properties
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, rows=rows).consume()
        return len(rows)

    def upsert_relationships(self, relationships: Sequence[GraphRelationship]) -> int:
        if not relationships:
            return 0
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relationship in relationships:
            grouped[relationship.relationship].append(
                relationship.model_dump(mode="json", exclude={"relationship"})
            )
        with self.driver.session(database=self.database) as session:
            for relationship_type, rows in grouped.items():
                # The relationship type comes from the strict Literal allowlist.
                query = f"""
                UNWIND $rows AS row
                MATCH (source:Entity {{entity_id: row.source_id}})
                MATCH (target:Entity {{entity_id: row.target_id}})
                MERGE (source)-[edge:{relationship_type} {{
                    target_id: row.target_id, evidence_id: row.evidence_id
                }}]->(target)
                SET edge.confidence = row.confidence,
                    edge.observed_at = datetime(row.observed_at)
                SET edge += row.properties
                """
                session.run(query, rows=rows).consume()
        return len(relationships)

    def path(self, source_id: str, target_id: str, maximum_hops: int = 4) -> list[Edge]:
        if not 1 <= maximum_hops <= 8:
            raise ValueError("maximum_hops must be between 1 and 8")
        query = f"""
        MATCH path = shortestPath(
            (source:Entity {{entity_id: $source_id}})-[*1..{maximum_hops}]->
            (target:Entity {{entity_id: $target_id}})
        )
        RETURN [node IN nodes(path) | node.name] AS names,
               [edge IN relationships(path) |
                 {{kind: type(edge), mechanism: coalesce(edge.mechanism, 'documented relation')}}
               ] AS edges
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query, source_id=source_id, target_id=target_id).single()
        if record is None:
            return []
        names, relationships = record["names"], record["edges"]
        return [
            Edge(
                source=names[index],
                relationship=relationship["kind"],
                target=names[index + 1],
                mechanism=relationship["mechanism"],
            )
            for index, relationship in enumerate(relationships)
        ]
