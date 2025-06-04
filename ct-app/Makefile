.PHONY: run       
run:
	@./scripts/run.sh --env=staging --count=5 --deployment=green

.PHONY: endurance
endurance:
	@python -m tests_endurance --file .configs/endurance_rules.yaml

.PHONY: fmt
fmt:
	@uvx black .
	@uvx ruff check
	@#uvx ty check core --ignore unresolved-import --ignore call-possibly-unbound-method --ignore possibly-unbound-attribute

.PHONY: test
test:
	@uv run -m pytest