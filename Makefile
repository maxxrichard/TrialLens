PYTHON ?= python
RAW_DIR ?= data/raw
OUT_DIR ?= data/out
PATIENTS ?= 200

.PHONY: install data run validate lint test test-e2e functions-install functions-test ci clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

data:
	$(PYTHON) -m triallens.local.synthetic --out $(RAW_DIR) --patients $(PATIENTS) --seed 7

run: data
	$(PYTHON) -m triallens.local.cli --raw $(RAW_DIR) --out $(OUT_DIR)

validate:
	$(PYTHON) tools/validate_specs.py

lint:
	ruff check .

test:
	pytest -m "not e2e"

test-e2e:
	pytest -m e2e

functions-install:
	cd functions-typescript && npm install --no-audit --no-fund

functions-test:
	cd functions-typescript && npm run lint && npm test

ci: lint validate test test-e2e functions-test

clean:
	rm -rf data spark-warehouse .pytest_cache .ruff_cache functions-typescript/dist
