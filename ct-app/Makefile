.PHONY: run       
run:
	@./scripts/run.sh --env=staging --deployment=green

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black core scripts test
	@uvx ruff check core scripts test
	@uvx ty check core scripts test
	@uv run scripts/verify_config.py -f .configs/core_prod_config.yaml -f .configs/core_staging_config.yaml -f test/test_config.yaml

.PHONY: test
test:
	@uv run pytest --cov=core --cov-report html:.coveragehtml