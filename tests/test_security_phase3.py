from pathlib import Path

from scripts.security_phase3 import scan_secrets


def test_secret_scanner_reports_location_without_exposing_value(tmp_path: Path) -> None:
    credential = "AKIA" + "ABCDEFGHIJKLMNOP"
    (tmp_path / "bad.py").write_text(f'value = "{credential}"\n', encoding="utf-8")
    findings = scan_secrets(tmp_path)
    assert findings == [{"type": "aws_access_key", "path": "bad.py", "line": 1}]
    assert "AKIA" not in str(findings)
