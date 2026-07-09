import io
import json
from urllib.error import URLError

import pytest

from aurum.data.lake import LakeLayer, LocalDataLake, QualityMetrics
from aurum.data.resilience import (
    ConnectorError,
    ResilientJSONClient,
    ResponseCache,
    TokenBucket,
    redact_url,
)


def quality(rows: int = 1) -> QualityMetrics:
    return QualityMetrics(
        row_count=rows,
        missing_values=0,
        duplicate_rows=0,
        schema_valid=True,
        chronological=True,
        quality_score=1,
    )


def test_data_lake_is_content_addressed_and_tracks_lineage(tmp_path) -> None:
    lake = LocalDataLake(tmp_path / "lake")
    raw = lake.write_raw(
        "prices",
        b'{"price":100}',
        source="test",
        quality=quality(),
    )
    duplicate = lake.write_raw(
        "prices",
        b'{"price":100}',
        source="test",
        quality=quality(),
    )
    assert raw.version == duplicate.version
    normalized = lake.write_derived(
        "prices",
        LakeLayer.NORMALIZED,
        b'[{"value":100.0}]',
        parent=raw,
        transformation="normalize-price",
        transformation_version="1.0.0",
        configuration={"unit": "USD"},
        quality=quality(),
    )
    assert normalized.parent_sha256 == raw.content_sha256
    assert normalized.configuration_sha256
    assert lake.read(normalized) == b'[{"value":100.0}]'


def test_data_lake_detects_corruption_and_unsafe_identifiers(tmp_path) -> None:
    lake = LocalDataLake(tmp_path / "lake")
    manifest = lake.write_raw("safe", b"original", source="test", quality=quality())
    data_path = lake.root / LakeLayer.RAW.value / "safe" / manifest.version / "data.bin"
    data_path.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="integrity"):
        lake.read(manifest)
    with pytest.raises(ValueError, match="unsafe"):
        lake.write_raw("../escape", b"x", source="test", quality=quality())


def test_resilient_client_retries_validates_and_caches(tmp_path, monkeypatch) -> None:
    attempts = 0

    def transport(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise URLError("temporary")
        return io.BytesIO(json.dumps({"ok": True}).encode())

    monkeypatch.setattr("aurum.data.resilience.time.sleep", lambda _: None)
    client = ResilientJSONClient(
        requests_per_second=1000,
        retries=1,
        cache=ResponseCache(tmp_path / "cache"),
        transport=transport,
    )
    assert client.get("https://example.test", validator=lambda value: value["ok"]) == {"ok": True}
    assert client.get("https://example.test") == {"ok": True}
    assert attempts == 2


def test_resilient_client_fails_closed_on_bad_schema(tmp_path) -> None:
    client = ResilientJSONClient(
        retries=0,
        cache=ResponseCache(tmp_path / "cache"),
        transport=lambda request, timeout: io.BytesIO(b'{"ok":false}'),
    )
    with pytest.raises(ConnectorError, match="after 1 attempts"):
        client.get("https://example.test", validator=lambda value: value["ok"])


def test_response_cache_json_bytes_and_secret_redaction(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    cache.put("json", {"ok": True})
    cache.put_bytes("bytes", b"payload")
    assert cache.get("json", 60) == {"ok": True}
    assert cache.get_bytes("bytes", 60) == b"payload"
    redacted = redact_url("https://x.test?a=1&apikey=secret&token=hidden")
    assert "secret" not in redacted and "hidden" not in redacted
    with pytest.raises(ValueError):
        TokenBucket(0)
    with pytest.raises(ValueError, match="invalid resilience"):
        ResilientJSONClient(retries=-1)


def test_resilient_client_rejects_empty_and_invalid_json(tmp_path) -> None:
    empty = ResilientJSONClient(
        retries=0,
        cache=ResponseCache(tmp_path / "empty"),
        transport=lambda request, timeout: io.BytesIO(b""),
    )
    with pytest.raises(ConnectorError, match="after 1 attempts"):
        empty.get_bytes("https://example.test")
    invalid = ResilientJSONClient(
        retries=0,
        cache=ResponseCache(tmp_path / "invalid"),
        transport=lambda request, timeout: io.BytesIO(b"not-json"),
    )
    with pytest.raises(ConnectorError):
        invalid.get("https://example.test")
