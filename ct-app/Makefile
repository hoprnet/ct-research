.PHONY: run
run:
	@./scripts/run.sh --env=staging --deployment=green

.PHONY: endurance
endurance:
	@uv run python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black core scripts test
	@ruff check core scripts test
	@uvx mypy
	@uv run scripts/verify_config.py -f .configs/core_prod_config.yaml -f .configs/core_staging_config.yaml -f test/test_config.yaml

.PHONY: test
test:
	@uv run pytest -m "not stress" --cov=core --cov-report html:.coveragehtml

.PHONY: stress
stress:
	@uv run pytest -m stress
