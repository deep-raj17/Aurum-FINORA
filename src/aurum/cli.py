"""Operational command-line interface."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .config import Settings
from .data import CSVProvider, DataPoint, SyntheticProvider
from .models import ForecastRequest
from .reporting import render_markdown
from .retrieval import Document
from .service import FinoraService


def _settings(path: str) -> Settings:
    candidate = Path(path)
    return Settings.from_yaml(candidate) if candidate.exists() else Settings()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aurum", description="FINORA operations CLI")
    parser.add_argument("--config", default="config/settings.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run seeded offline analysis")
    demo.add_argument("--days", type=int, default=180)
    demo.add_argument("--horizon", type=int, default=5)
    demo.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="explicitly authorize development-only simulated data",
    )
    forecast = subparsers.add_parser("forecast", help="forecast a normalized CSV series")
    forecast.add_argument("csv")
    forecast.add_argument("--target", required=True)
    forecast.add_argument("--horizon", type=int, default=5)
    forecast.add_argument("--evidence-query")
    forecast.add_argument("--output", choices=["json", "markdown"], default="markdown")
    ingest = subparsers.add_parser("ingest", help="index an evidence document")
    ingest.add_argument("file")
    ingest.add_argument("--origin", required=True)
    ingest.add_argument("--published-at", required=True)
    subparsers.add_parser("audit", help="verify the immutable audit chain")
    kdq_generate = subparsers.add_parser(
        "kdq-generate", help="generate versioned teacher soft labels"
    )
    kdq_generate.add_argument("--settings", default="config/kdq.yaml")
    kdq_generate.add_argument("--output", default="data/kdq/offline-smoke.jsonl")
    kdq_generate.add_argument("--count", type=int, default=96)
    kdq_generate.add_argument(
        "--allow-offline-baselines",
        action="store_true",
        help="explicitly authorize CI/smoke teachers; never use for validated artifacts",
    )
    kdq_train = subparsers.add_parser("kdq-train", help="train the distilled QAT student")
    kdq_train.add_argument("dataset")
    kdq_train.add_argument("--settings", default="config/kdq.yaml")
    kdq_export = subparsers.add_parser("kdq-export", help="export a governed student artifact")
    kdq_export.add_argument("artifact")
    kdq_export.add_argument("--format", choices=["int8", "torchscript", "onnx"], default="int8")
    kdq_export.add_argument("--output")
    kdq_info = subparsers.add_parser("kdq-info", help="inspect a KD-Q artifact manifest")
    kdq_info.add_argument("artifact")
    return parser


def _request_from_points(target: str, horizon: int, points: list[DataPoint]) -> ForecastRequest:
    last_date = max(point.timestamp.date() for point in points)
    return ForecastRequest(
        target=target,
        values=[point.value for point in points],
        dates=[point.timestamp.date() for point in points],
        horizon=horizon,
        forecast_start=datetime.combine(last_date + timedelta(days=1), datetime.min.time(), UTC),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = FinoraService(_settings(args.config))
    if args.command == "demo":
        if not args.allow_synthetic:
            raise SystemExit(
                "demo uses simulated data; pass --allow-synthetic or use `aurum forecast`"
            )
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=args.days - 1)
        points = SyntheticProvider().fetch("SYNTHETIC_INDEX", start, end)
        report = service.analyse(_request_from_points("SYNTHETIC_INDEX", args.horizon, points))
        print(render_markdown(report))
        return 0
    if args.command == "forecast":
        points = CSVProvider(args.csv).fetch(args.target, date.min, date.max)
        if not points:
            raise SystemExit("CSV produced no observations")
        report = service.analyse(
            _request_from_points(args.target, args.horizon, points),
            args.evidence_query,
        )
        print(
            report.model_dump_json(indent=2) if args.output == "json" else render_markdown(report)
        )
        return 0
    if args.command == "ingest":
        published_at = datetime.fromisoformat(args.published_at.replace("Z", "+00:00"))
        service.add_evidence(
            Document(
                origin=args.origin,
                published_at=published_at,
                text=Path(args.file).read_text(encoding="utf-8"),
            )
        )
        print("indexed")
        return 0
    if args.command == "audit":
        valid = service.repository.verify_audit_chain()
        print("valid" if valid else "INVALID")
        return 0 if valid else 1
    if args.command == "kdq-generate":
        if not args.allow_offline_baselines:
            raise SystemExit(
                "production distillation requires configured teacher models; "
                "pass --allow-offline-baselines only for CI/smoke artifacts"
            )
        import yaml

        from .kdq.config import KDQConfig
        from .kdq.data import build_distilled_sample, synthetic_teacher_inputs, write_jsonl
        from .kdq.teachers import TeacherEnsemble

        payload = yaml.safe_load(Path(args.settings).read_text(encoding="utf-8"))
        model_config = KDQConfig.model_validate(payload["model"])
        ensemble = TeacherEnsemble(
            reasoning_size=model_config.reasoning_size,
            allow_offline_baselines=True,
        )
        samples = [
            build_distilled_sample(
                raw,
                target_return=target_return,
                target_volatility=target_volatility,
                ensemble=ensemble,
                config=model_config,
            )
            for raw, target_return, target_volatility in synthetic_teacher_inputs(
                model_config, args.count
            )
        ]
        digest = write_jsonl(samples, args.output)
        print(json.dumps({"samples": len(samples), "sha256": digest, "path": args.output}))
        return 0
    if args.command == "kdq-train":
        import yaml

        from .kdq.config import KDQConfig, TrainingConfig
        from .kdq.data import read_jsonl
        from .kdq.training import train_student

        payload = yaml.safe_load(Path(args.settings).read_text(encoding="utf-8"))
        result = train_student(
            read_jsonl(args.dataset),
            KDQConfig.model_validate(payload["model"]),
            TrainingConfig.model_validate(payload["training"]),
        )
        print(
            json.dumps(
                {
                    "artifact": str(result.artifact_dir),
                    "best_validation_loss": result.best_validation_loss,
                    "epochs": result.epochs_completed,
                }
            )
        )
        return 0
    if args.command == "kdq-export":
        from .kdq.export import (
            export_int8_torchscript,
            export_onnx,
            export_torchscript,
            load_artifact,
        )

        artifact = Path(args.artifact)
        model = load_artifact(artifact)
        suffix = "onnx" if args.format == "onnx" else "pt"
        output = Path(args.output or artifact / f"finora-kdq.{suffix}")
        if args.format == "onnx":
            exported = export_onnx(model, output)
        elif args.format == "int8":
            exported = export_int8_torchscript(model, output)
        else:
            exported = export_torchscript(model, output)
        print(str(exported))
        return 0
    if args.command == "kdq-info":
        manifest = Path(args.artifact) / "manifest.json"
        print(json.dumps(json.loads(manifest.read_text(encoding="utf-8")), indent=2))
        return 0
    return 2
