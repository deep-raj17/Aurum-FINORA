# Aurum / FINORA — developer task runner
# Usage: make <target>   (on Windows, install GNU make or run the commands directly)

.PHONY: help install install-all demo test quality lint format typecheck api audit docker kdq-generate kdq-train kdq-export kdq-deploy live-test model-test research-validate load-test security-phase3 clean validate-providers-live validate-real-models benchmark-rtx4070 loadtest-staging dr-drill-local validate-ingress-security

help:
	@echo "Aurum / FINORA targets:"
	@echo "  install      Install core + stats + data deps (editable)"
	@echo "  install-all  Install full stack incl. deep/rag/serve"
	@echo "  demo         Run an explicitly marked simulated development smoke"
	@echo "  test         Run pytest suite"
	@echo "  quality      Run the full local quality gate"
	@echo "  lint         Ruff lint"
	@echo "  format       Ruff format"
	@echo "  typecheck    Mypy static type check"
	@echo "  api          Launch FastAPI dev server"
	@echo "  audit        Verify the hash-chained audit log"
	@echo "  docker       Build and run the local service stack"
	@echo "  kdq-generate Generate explicitly marked offline smoke labels"
	@echo "  kdq-train    Train FINORA-KD-Q from generated labels"
	@echo "  kdq-export   Export the trained student to hybrid INT8"
	@echo "  kdq-deploy   Copy the artifact into Docker's named volume"
	@echo "  live-test    Run explicitly enabled credentialed provider tests"
	@echo "  model-test   Run explicitly enabled real-weight model tests"
	@echo "  research-validate Run real-data walk-forward validation"
	@echo "  load-test    Run a short local Locust validation"
	@echo "  security-phase3 Run dependency, secret and image scans"
	@echo "  validate-providers-live Phase 4: Run live provider validation with credential checks"
	@echo "  validate-real-models   Phase 4: Validate real model weights and checksums"
	@echo "  benchmark-rtx4070      Phase 4: Run RTX 4070 GPU benchmark suite"
	@echo "  loadtest-staging      Phase 4: Run sustained staging load tests"
	@echo "  dr-drill-local         Phase 4: Run local disaster recovery drills"
	@echo "  validate-ingress-security Phase 4: Validate authenticated ingress security"
	@echo "  clean        Remove caches and build artifacts"

install:
	pip install -e ".[stats,data,dev]"

install-all:
	pip install -e ".[all]"

demo:
	aurum demo --allow-synthetic

test:
	pytest -q

quality: lint typecheck test
	ruff format --check src tests scripts

lint:
	ruff check src tests scripts

format:
	ruff format src tests scripts

typecheck:
	mypy src

api:
	uvicorn aurum.api.main:app --reload

audit:
	aurum audit

docker:
	docker compose up --build

kdq-generate:
	aurum kdq-generate --settings config/kdq-smoke.yaml --output data/kdq/offline-smoke.jsonl --allow-offline-baselines

kdq-train:
	aurum kdq-train data/kdq/training.jsonl --settings config/kdq.yaml

kdq-export:
	aurum kdq-export artifacts/finora-kdq --format int8

kdq-deploy:
	python scripts/deploy_kdq_artifact.py artifacts/finora-kdq

live-test:
	pytest -m live tests/integration/test_live_providers.py -ra

model-test:
	pytest -m model tests/integration/test_real_models.py -ra

research-validate:
	python scripts/run_research_validation.py --provider yahoo --symbol AAPL --model xgboost

load-test:
	locust -f load/locustfile.py --headless -u 5 -r 2 --run-time 30s --host http://localhost:8000

security-phase3:
	python scripts/security_phase3.py --image aurum-aurum:latest

clean:
	python -c "import shutil,glob,os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True)]"
	python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache','.mypy_cache','.ruff_cache','build','dist']]"

# Phase 4: Staging Validation Commands

validate-providers-live:
	@mkdir -p reports/providers
	@echo "Running live provider validation..."
	FINORA_RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_live_providers.py -ra --json-report --json-report-file=reports/providers/live_provider_validation.json
	@echo "Live provider validation complete. Results saved to reports/providers/"
	@echo "See reports/providers/live_provider_validation.md for summary"

validate-real-models:
	@mkdir -p reports/models
	@echo "Running real model validation..."
	FINORA_RUN_MODEL_TESTS=1 pytest -m model tests/integration/test_real_models.py -ra --json-report --json-report-file=reports/models/real_model_validation.json
	@echo "Real model validation complete. Results saved to reports/models/"
	@echo "See reports/models/real_model_validation.md for summary"

benchmark-rtx4070:
	@mkdir -p reports/benchmarks
	@echo "Running RTX 4070 benchmark suite..."
	python scripts/benchmark_phase3.py artifacts/finora-kdq-smoke --model artifacts/finora-kdq-smoke/finora-kdq-fp32.pt --output reports/benchmarks/rtx4070 --device cuda --precision fp16
	@echo "Benchmark complete. Results saved to reports/benchmarks/"

loadtest-staging:
	@mkdir -p reports/loadtest
	@echo "Running staging load test..."
	@if [ -z "$(STAGING_API_URL)" ]; then \
		echo "Error: STAGING_API_URL environment variable not set"; \
		exit 1; \
	fi
	locust -f load/locustfile.py --headless -u 50 -r 10 --run-time 3600s --host $(STAGING_API_URL) --csv reports/loadtest/staging_load_test
	@echo "Load test complete. Results saved to reports/loadtest/"

dr-drill-local:
	@mkdir -p reports/dr
	@echo "Running local disaster recovery drill..."
	python scripts/disaster_recovery.py --output reports/dr/dr_drill_report.json
	@echo "DR drill complete. Results saved to reports/dr/"

validate-ingress-security:
	@mkdir -p reports/security
	@echo "Validating authenticated ingress security..."
	python scripts/security_phase3.py --ingress-only --output reports/security/ingress_validation.json
	@echo "Ingress security validation complete. Results saved to reports/security/"
