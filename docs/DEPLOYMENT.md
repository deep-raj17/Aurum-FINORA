# FINORA production deployment

## Validate

```bash
ruff check src tests scripts
mypy src
pytest --cov=aurum --cov-fail-under=95
docker build -t registry.example/finora:RELEASE_SHA .
python scripts/security_phase3.py --image registry.example/finora:RELEASE_SHA
```

## Kubernetes and Helm

Raw manifests are under `k8s/base`; the configurable chart is `helm/finora`.

```bash
kubectl apply --server-side --dry-run=server -k k8s/base
helm lint helm/finora
helm template finora-blue helm/finora --set image.tag=RELEASE_SHA
helm upgrade --install finora-blue helm/finora --namespace finora --atomic --wait
```

Use an existing external secret or secrets operator. Never commit a Secret manifest.
GPU workloads require vendor drivers/device plugin and `gpu.enabled=true`.

## Blue-green and rollback

Deploy the inactive color with a distinct Helm release, run readiness/live/model
validation, then atomically change the Service selector to the new color. Retain the
previous Deployment until the observation window passes. Roll back by restoring the
old selector or `helm rollback RELEASE REVISION --wait`.

## Terraform

```bash
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=finora.plan
terraform apply finora.plan
```

Use encrypted, locked remote state. The optional EKS GPU node group needs existing
cluster, subnet and IAM role identifiers. Terraform variables containing secrets must
come from the secret manager/CI and state access must be restricted.

## Observability and recovery

Prometheus scrapes `/metrics`; the chart can create a ServiceMonitor when the CRD is
installed. Alert on error/latency saturation, open circuits, drift, failed audit chain,
GPU memory, and unavailable dependencies. Perform a verified snapshot/restore drill
before each production release and measure RPO/RTO.
