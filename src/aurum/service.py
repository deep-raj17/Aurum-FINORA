"""Application service coordinating retrieval, analysis, persistence, and reports."""

from __future__ import annotations

from .config import Settings
from .models import AnalysisReport, ForecastRequest
from .pipeline import FinoraPipeline
from .reporting import render_markdown
from .retrieval import Document, InMemoryRetriever
from .storage import Repository


class FinoraService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: Repository | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.repository = repository or Repository(self.settings.database_path)
        self.pipeline = FinoraPipeline(self.settings)

    def add_evidence(self, document: Document) -> None:
        self.repository.add_document(document)
        self.repository.append_audit(
            "evidence.added",
            {"origin": document.origin, "published_at": document.published_at.isoformat()},
        )

    def analyse(
        self, request: ForecastRequest, evidence_query: str | None = None
    ) -> AnalysisReport:
        citations = []
        if evidence_query:
            retriever = InMemoryRetriever(self.repository.load_documents())
            citations = retriever.search(
                evidence_query,
                as_of=request.forecast_start,
                limit=self.settings.retrieval_limit,
            )
        report = self.pipeline.run(request, citations)
        self.repository.save_report(report)
        return report

    def markdown_report(self, run_id: str) -> str | None:
        report = self.repository.get_report(run_id)
        return render_markdown(report) if report else None
