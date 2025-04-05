.PHONY: run       
run:
	@./scripts/run.sh

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