"""Directed relationship graph and explicit contagion-path traversal."""

from __future__ import annotations

from collections import defaultdict, deque

from pydantic import BaseModel


class Edge(BaseModel):
    source: str
    relationship: str
    target: str
    mechanism: str


class EntityGraph:
    def __init__(self, edges: list[Edge] | None = None) -> None:
        self._edges: dict[str, list[Edge]] = defaultdict(list)
        for edge in edges or []:
            self.add(edge)

    def add(self, edge: Edge) -> None:
        self._edges[edge.source].append(edge)

    def path(self, source: str, target: str) -> list[Edge]:
        queue: deque[tuple[str, list[Edge]]] = deque([(source, [])])
        visited = {source}
        while queue:
            node, path = queue.popleft()
            for edge in self._edges[node]:
                next_path = [*path, edge]
                if edge.target == target:
                    return next_path
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, next_path))
        return []

    def describe_path(self, source: str, target: str) -> str:
        path = self.path(source, target)
        if not path:
            return f"CONTAGION PATH: no documented path from {source} to {target}"
        parts = [path[0].source]
        for edge in path:
            parts.extend([f"—{edge.relationship}→", edge.target, f"({edge.mechanism})"])
        return "CONTAGION PATH: " + " ".join(parts)

    def critical_nodes(self, limit: int = 10) -> list[tuple[str, int]]:
        degree: dict[str, int] = defaultdict(int)
        for source, edges in self._edges.items():
            degree[source] += len(edges)
            for edge in edges:
                degree[edge.target] += 1
        return sorted(degree.items(), key=lambda item: (-item[1], item[0]))[:limit]
