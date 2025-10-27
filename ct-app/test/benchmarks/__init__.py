"""
Benchmark suite for message processing performance.

This module provides comprehensive benchmarking tools to measure:
- Sustained throughput over time
- Queue depth and backpressure
- Per-message latency distributions
- System limits and breaking points
- Phase 1 optimization improvements
"""

__all__ = ["MetricsCollector", "BenchmarkConfig", "generate_report"]
