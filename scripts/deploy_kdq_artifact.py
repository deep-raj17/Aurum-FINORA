"""Copy a governed FINORA-KD-Q artifact into Docker's named deployment volume."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=check, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", help="artifact directory containing manifest.json")
    parser.add_argument("--volume", default="aurum_aurum_kdq_artifacts")
    arguments = parser.parse_args()
    artifact = Path(arguments.artifact).resolve()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", artifact.name):
        raise SystemExit("artifact directory name contains unsupported characters")
    manifest_path = artifact / "manifest.json"
    checkpoint = artifact / "student-state.pt"
    if not manifest_path.is_file() or not checkpoint.is_file():
        raise SystemExit("artifact must contain manifest.json and student-state.pt")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("deployment_status") != "REQUIRES_HUMAN_VALIDATION":
        print(f"deploying artifact status: {manifest.get('deployment_status')}")
    docker = shutil.which("docker")
    if docker is None:
        raise SystemExit("docker CLI is not available on PATH")
    helper = "finora-kdq-artifact-seed"
    run(docker, "rm", "-f", helper, check=False)
    run(docker, "volume", "create", arguments.volume)
    run(
        docker,
        "run",
        "--rm",
        "-v",
        f"{arguments.volume}:/app/artifacts",
        "alpine:3.21",
        "rm",
        "-rf",
        f"/app/artifacts/{artifact.name}",
    )
    try:
        run(
            docker,
            "create",
            "--name",
            helper,
            "-v",
            f"{arguments.volume}:/app/artifacts",
            "alpine:3.21",
        )
        run(
            docker,
            "cp",
            str(artifact),
            f"{helper}:/app/artifacts/{artifact.name}",
        )
    finally:
        run(docker, "rm", "-f", helper, check=False)
    print(
        json.dumps(
            {
                "artifact": artifact.name,
                "volume": arguments.volume,
                "status": manifest.get("deployment_status"),
                "checkpoint_sha256": manifest.get("checkpoint_sha256"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
