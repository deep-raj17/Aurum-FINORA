"""Dataset identity and manifest validation helpers for RP1 research controls."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST_COLUMNS = {
    "symbol",
    "safe_name",
    "category",
    "source",
    "start_date",
    "end_date",
}

PUBLICATION_REQUIRED_COLUMNS = REQUIRED_MANIFEST_COLUMNS | {
    "frequency",
    "row_count",
    "schema_version",
    "dataset_version",
    "retrieval_timestamp",
    "raw_sha256",
    "processed_sha256",
    "timezone",
    "adjusted_price_status",
    "file_path",
}


@dataclass(frozen=True)
class ManifestIssue:
    field: str
    status: str
    message: str
    severity: str = "High"


@dataclass(frozen=True)
class ManifestRowValidation:
    row_number: int
    symbol: str
    safe_name: str
    category: str
    file_path: Path | None
    file_sha256: str | None
    status: str
    issues: tuple[ManifestIssue, ...] = field(default_factory=tuple)

    @property
    def publication_safe(self) -> bool:
        return self.status == "valid"


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonicalize_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"), default=str)


def stable_seed(value: str, *, modulo: int = 2**32) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulo


def is_latest(value: object) -> bool:
    return str(value).strip().lower() == "latest"


def dataset_version(
    *,
    provider: str,
    asset: str,
    frequency: str,
    start_date: str,
    end_date: str,
    retrieval_date: str,
    file_hash: str,
) -> str:
    if is_latest(end_date):
        raise ValueError("end_date must be immutable; 'latest' is not publication-safe")
    if not file_hash:
        raise ValueError("file_hash is required")
    parts = [provider, asset, frequency, start_date, end_date, retrieval_date, file_hash[:12]]
    normalized = ["_".join(re.findall(r"[A-Za-z0-9]+", str(part))).strip("_") for part in parts]
    if any(not part for part in normalized):
        raise ValueError("dataset version fields must be non-empty")
    return "_".join(normalized)


def infer_data_file(row: dict[str, str], root: str | Path = ".") -> Path:
    if row.get("file_path"):
        return Path(root) / row["file_path"]
    return Path(root) / "data" / row["category"] / f"{row['safe_name']}.csv"


def validate_manifest_row(
    row: dict[str, str],
    *,
    row_number: int,
    root: str | Path = ".",
    publication_schema: bool = True,
    compute_hash: bool = True,
) -> ManifestRowValidation:
    required = PUBLICATION_REQUIRED_COLUMNS if publication_schema else REQUIRED_MANIFEST_COLUMNS
    issues: list[ManifestIssue] = []
    for column in sorted(required):
        if column not in row:
            issues.append(ManifestIssue(column, "absent", "required column is missing"))
        elif str(row.get(column, "")).strip() == "":
            issues.append(ManifestIssue(column, "invalid", "required value is empty"))

    if "end_date" in row and is_latest(row.get("end_date")):
        issues.append(
            ManifestIssue(
                "end_date",
                "invalid",
                "'latest' is non-immutable and publication-unsafe",
                "Critical",
            )
        )

    file_path: Path | None = None
    file_hash: str | None = None
    if {"category", "safe_name"}.issubset(row):
        file_path = infer_data_file(row, root)
        if not file_path.exists():
            issues.append(
                ManifestIssue("file_path", "invalid", f"referenced file not found: {file_path}")
            )
        elif compute_hash:
            file_hash = sha256_file(file_path)

    for date_field in ("start_date", "end_date"):
        value = row.get(date_field)
        if value and not is_latest(value):
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                issues.append(
                    ManifestIssue(date_field, "invalid", "date must use YYYY-MM-DD format")
                )

    status = "valid" if not issues else "invalid"
    return ManifestRowValidation(
        row_number=row_number,
        symbol=row.get("symbol", ""),
        safe_name=row.get("safe_name", ""),
        category=row.get("category", ""),
        file_path=file_path,
        file_sha256=file_hash,
        status=status,
        issues=tuple(issues),
    )


def validate_manifest_file(
    path: str | Path,
    *,
    root: str | Path = ".",
    publication_schema: bool = True,
    compute_hashes: bool = True,
) -> list[ManifestRowValidation]:
    manifest = Path(path)
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            validate_manifest_row(
                row,
                row_number=index,
                root=root,
                publication_schema=publication_schema,
                compute_hash=compute_hashes,
            )
            for index, row in enumerate(reader, start=2)
        ]


def duplicate_dataset_identities(rows: list[ManifestRowValidation]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        identity = f"{row.category}:{row.safe_name}:{row.file_sha256 or 'missing'}"
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)
    return duplicates
