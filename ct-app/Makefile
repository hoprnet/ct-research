.PHONY: run       
run:
	@./scripts/run.sh --env=staging --count=1

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx ruff check
	@uvx black .

.PHONY: test
test:
	pytest