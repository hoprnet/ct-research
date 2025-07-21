.PHONY: run       
run:
	@./scripts/run.sh --env=staging --count=5

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black core test
	@uvx ruff check core test
	@uvx ty check core test

.PHONY: test
test:
	uv run -m pytest