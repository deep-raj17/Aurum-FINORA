# Troubleshooting

## Windows pyarrow collection issue

Phase 6 documented a native Windows `pyarrow` access-violation trace during pytest
collection. Phase 7 tested the local environment with `pyarrow 24.0.0`, then pinned
the validation extras to `pyarrow==16.1.0`. With that pin, `pytest -q -ra` passed with
131 passed and 26 skipped.

Recommended action:

```powershell
pip install "pyarrow==16.1.0"
pip install -e ".[dev,kdq,data]"
pytest -q -ra
```

If the native Windows issue recurs, use WSL/Linux as the recommended validation
environment. The Phase 6 local graph/vector service validation already used WSL2 for
Docker Engine and Compose.

## API health reachability

The `/health` endpoint is implemented and tested. For runtime verification, start the
API from the repository root:

```powershell
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port 8000
```

Then verify:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Expected fields:

- `status`: `ok`
- `mode`: `decision-support`
- `audit_chain_valid`: `True`

If production mode is enabled, configure `AURUM_API_KEY` or `AURUM_API_KEY_FILE`.
Local development mode does not require an API key for `/health`.

## Mypy timeout-safe validation

Plain `mypy src` may appear to hang in some Windows shells. Use a process-based timeout
guard:

```powershell
$p = Start-Process -FilePath mypy -ArgumentList 'src' -PassThru -NoNewWindow
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'mypy timed out after 60 seconds' }
if ($p.ExitCode -ne 0) { throw "mypy failed with exit code $($p.ExitCode)" }
```

Phase 7 result: `Success: no issues found in 74 source files`.
