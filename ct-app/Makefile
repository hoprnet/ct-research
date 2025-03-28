.PHONY: run       
run:
	@./scripts/run.sh staging 5

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@black .
	@ruff check .

.PHONY: test
test:
	pytest