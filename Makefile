.PHONY: qa format lint typecheck test security
.DEFAULT_GOAL := qa

qa: format lint typecheck test security  ## Run full QA suite

format:  ## Format source code
	@uv run ruff format src tests

lint:  ## Lint source and tests
	@uv run ruff check src tests

typecheck:  ## Type-check source code
	@uv run mypy src

test:  ## Run test suite with coverage
	@uv run pytest --cov=src/ralph -v

security:  ## Run bandit security scanner
	@uv run bandit -r src

clean:  ## Remove build artifacts and cache
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info
