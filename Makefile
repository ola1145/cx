.PHONY: setup lint typecheck test test-ws test-infra schemas contract-test build synth synth-all validate diff eval e2e clean

setup:
	uv sync --all-packages
	npm ci

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy contracts/src lib/src infra

test:
	uv run pytest lib/ tests/contract/ -x --tb=short -m "not live"

test-ws:
	@[ "$(WS)" != "" ] || (echo "Usage: make test-ws WS=ws1-channels" && exit 1)
	uv run pytest $(WS)/tests/ -x --tb=short -m "not live"

test-infra:
	uv run pytest tests/infra/ -x --tb=short

schemas:
	uv run python tools/export_schemas.py

contract-test:
	uv run pytest tests/contract/ -x --tb=short

build:
	mkdir -p build
	@echo "Lambda packaging placeholder — implement per-ws build steps"

synth:
	cd infra && npx cdk synth --strict -c env=$(or $(ENV),sandbox) --quiet

synth-all:
	cd infra && npx cdk synth --strict -c env=sandbox --quiet
	cd infra && npx cdk synth --strict -c env=staging --quiet
	cd infra && npx cdk synth --strict -c env=prod --quiet

validate: synth-all

diff:
	cd infra && npx cdk diff -c env=$(or $(ENV),sandbox)

eval:
	uv run pytest ws2-spine/evals/ -x --tb=short -m "not live"

e2e:
	@if [ "$(E2E)" != "1" ]; then echo "Skipped. Use: make e2e E2E=1"; exit 0; fi
	uv run pytest tests/e2e/ -x --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null; true
	rm -rf infra/cdk.out build .coverage .pytest_cache
