.PHONY: run       
run:
	@./scripts/run.sh --env=staging --count=5 --deployment=green

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black core scripts test
	@uvx ruff check core scripts test
	@uvx ty check core scripts test

.PHONY: test
test:
	@uv run pytest --cov=core --cov-report html:.coveragehtml