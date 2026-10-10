# Cloud Assessor App (appliance edition). Every target is a plain uv invocation; `make run` is the only one that can
# reach Azure, and only through the signed-in `az login` session or a managed identity (identity.py).
.PHONY: setup lock lint test test-security run image-appliance image-lab clean

setup:
	uv python pin 3.14.6
	uv sync --all-packages --extra azure

lock:
	uv lock
	uv export --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -o requirements.lock.txt
	uv export --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header --extra azure -o requirements-azure.lock.txt

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/check-catalog.py
	uv run python scripts/check-docs-governance.py
	bash scripts/check-versions.sh
	bash scripts/check-lockfiles.sh

test:
	uv run pytest -q --cov=packages --cov=src --cov-report=term-missing

test-security:
	uv run pytest tests/security tests/packaging -q

run:
	PORT=8080 uv run --extra azure python -m cloud_assessor_appliance

image-appliance:
	docker build -f infrastructure/docker/Dockerfile --target appliance -t hcw-cloud-assessor-appliance:dev .

image-lab:
	docker build -f infrastructure/docker/Dockerfile --target lab -t hcw-cloud-assessor-lab:dev .
	docker run --rm hcw-cloud-assessor-lab:dev

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage coverage.xml htmlcov dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
