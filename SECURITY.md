# FINORA security policy

Report vulnerabilities privately to repository maintainers. Never place API keys,
client data, unpublished filings, positions, model weights, or approval credentials in
issues, logs, benchmark reports, or source control.

Production controls:

- TLS and OAuth/OIDC at the ingress; JWT issuer, audience, signature, expiry, and role
  verification before FINORA authorization.
- Mounted secret files or an external secret manager; no secrets in images, ConfigMaps,
  Terraform state without encrypted remote state, or Helm values.
- Restricted Kubernetes Pod Security, non-root/read-only containers, dropped Linux
  capabilities, network policies, image digest pinning, and signed images.
- AES-256-GCM for sensitive application fields and encrypted storage/backups.
- Prompt-injection and RAG-poisoning inspection before indexing, content hashes, source
  allowlists, time cutoffs, and citation validation.
- Per-principal rate limits, circuit breakers, structured audit logs, and alerting.

Validation commands:

```bash
pip-audit -r requirements-api.txt
python scripts/security_phase3.py --image aurum-aurum:latest
pytest -m security
```

CI scans production dependencies and the built image for HIGH/CRITICAL findings. A
release is blocked if a vulnerability is unfixed and exploitable, a secret is detected,
JWT/RBAC or abuse tests fail, or the container scan is unavailable. See
[security validation](docs/PHASE3_PRODUCTION_VALIDATION.md#security).
