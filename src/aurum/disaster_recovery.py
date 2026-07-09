"""Verified SQLite and file-asset snapshots for disaster-recovery drills."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SnapshotFile(BaseModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)


class SnapshotManifest(BaseModel):
    snapshot_id: str
    created_at: datetime
    files: list[SnapshotFile]


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_snapshot(
    database: str | Path,
    asset_roots: list[str | Path],
    destination: str | Path,
) -> SnapshotManifest:
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=False)
    database_path = Path(database).resolve(strict=True)
    database_copy = target / "database.sqlite3"
    source = sqlite3.connect(database_path)
    output = sqlite3.connect(database_copy)
    try:
        source.backup(output)
    finally:
        output.close()
        source.close()
    files = [
        SnapshotFile(
            relative_path="database.sqlite3",
            sha256=_hash(database_copy),
            bytes=database_copy.stat().st_size,
        )
    ]
    assets = target / "assets"
    for root_value in asset_roots:
        root = Path(root_value).resolve(strict=True)
        root_target = assets / root.name
        shutil.copytree(root, root_target)
        for path in sorted(item for item in root_target.rglob("*") if item.is_file()):
            relative = path.relative_to(target).as_posix()
            files.append(
                SnapshotFile(
                    relative_path=relative,
                    sha256=_hash(path),
                    bytes=path.stat().st_size,
                )
            )
    created = datetime.now(UTC)
    snapshot_id = hashlib.sha256(f"{created.isoformat()}|{files}".encode()).hexdigest()[:20]
    manifest = SnapshotManifest(snapshot_id=snapshot_id, created_at=created, files=files)
    (target / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def verify_snapshot(snapshot: str | Path) -> SnapshotManifest:
    root = Path(snapshot).resolve(strict=True)
    manifest = SnapshotManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    for item in manifest.files:
        path = (root / item.relative_path).resolve(strict=True)
        if root not in path.parents or _hash(path) != item.sha256:
            raise RuntimeError(f"snapshot integrity failure: {item.relative_path}")
    return manifest


def restore_snapshot(
    snapshot: str | Path,
    database_destination: str | Path,
    asset_destination: str | Path,
) -> SnapshotManifest:
    manifest = verify_snapshot(snapshot)
    root = Path(snapshot).resolve(strict=True)
    db_target = Path(database_destination).resolve()
    db_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "database.sqlite3", db_target)
    assets_target = Path(asset_destination).resolve()
    assets_target.mkdir(parents=True, exist_ok=True)
    for source in (root / "assets").glob("*") if (root / "assets").exists() else []:
        destination = assets_target / source.name
        if destination.exists():
            raise FileExistsError(f"restore destination already exists: {destination}")
        shutil.copytree(source, destination)
    return manifest
