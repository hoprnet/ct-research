.PHONY: run       
run:
	@./scripts/run.sh --env=staging --count=5 --deployment=green

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black .
	@uvx ruff check .
	@uvx ty check .

.PHONY: test
test:
	@uv run pytest --cov=core --cov-report html:.coveragehtml