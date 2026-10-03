.PHONY: help install demo test lint scan adversaries clean
.DEFAULT_GOAL := help

PY ?= python

help:                ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:             ## Install the dev dependencies (runtime deps: none)
	$(PY) -m pip install -e ".[dev]" || uv pip install -e ".[dev]"

demo:                ## Build four real histories and score them (~5 s, no network)
	$(PY) demo.py

test:                ## Run the test suite
	$(PY) -m pytest -q

lint:                ## Check formatting and lint
	$(PY) -m ruff check src tests demo.py
	$(PY) -m ruff format --check src tests demo.py

scan:                ## Score every git repository under DIR (default: the parent directory)
	$(PY) src/score.py $(or $(DIR),..)

adversaries:         ## Build all 8 adversaries x 2 seeds + 3 controls and score them (~25 s)
	$(PY) src/adversaries.py

clean:               ## Remove caches
	rm -rf .pytest_cache .ruff_cache src/__pycache__ tests/__pycache__
