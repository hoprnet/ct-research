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

.PHONY: benchmark
benchmark:
	@echo "Running sustained load benchmarks (30 min)..."
	@uv run pytest test/benchmarks -m benchmark -v

.PHONY: benchmark-quick
benchmark-quick:
	@echo "Running quick benchmarks (5 min)..."
	@uv run pytest test/benchmarks/test_sustained_load.py::test_sustained_100_msg_per_sec -v --duration=60

.PHONY: benchmark-130
benchmark-130:
	@echo "Running 130 msg/sec benchmark (10 min)..."
	@uv run pytest test/benchmarks/test_sustained_load.py::test_sustained_130_msg_per_sec -v

.PHONY: benchmark-ramping
benchmark-ramping:
	@echo "Running ramping load test to find limits..."
	@uv run pytest test/benchmarks/test_ramping_load.py -v
