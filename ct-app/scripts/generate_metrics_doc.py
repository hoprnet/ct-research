import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

PROMETHEUS_TYPES = {"Gauge", "Counter", "Histogram", "Summary"}
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "core"
DEFAULT_OUTPUT = REPO_ROOT / "METRICS.md"


@dataclass(frozen=True)
class MetricDefinition:
    variable_name: str
    metric_type: str
    metric_name: str
    description: str
    labels: tuple[str, ...]
    source: str


def _extract_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_labels(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, (ast.List, ast.Tuple)):
        labels: list[str] = []
        for item in node.elts:
            value = _extract_string(item)
            if value is None:
                return ()
            labels.append(value)
        return tuple(labels)
    return ()


def _call_metric_type(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name) and call.func.id in PROMETHEUS_TYPES:
        return call.func.id
    if isinstance(call.func, ast.Attribute) and call.func.attr in PROMETHEUS_TYPES:
        return call.func.attr
    return None


def _extract_metric_from_assign(node: ast.Assign, source: Path) -> MetricDefinition | None:
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    if not isinstance(node.value, ast.Call):
        return None

    metric_type = _call_metric_type(node.value)
    if metric_type is None:
        return None

    if len(node.value.args) < 2:
        return None

    metric_name = _extract_string(node.value.args[0])
    description = _extract_string(node.value.args[1])
    if metric_name is None or description is None:
        return None

    labels: tuple[str, ...] = ()
    if len(node.value.args) >= 3:
        labels = _extract_labels(node.value.args[2])

    for keyword in node.value.keywords:
        if keyword.arg in {"labelnames", "labels"} and labels == ():
            labels = _extract_labels(keyword.value)

    return MetricDefinition(
        variable_name=node.targets[0].id,
        metric_type=metric_type,
        metric_name=metric_name,
        description=description,
        labels=labels,
        source=str(source.relative_to(REPO_ROOT)),
    )


def collect_metrics(source_root: Path = DEFAULT_SOURCE_ROOT) -> list[MetricDefinition]:
    metrics: list[MetricDefinition] = []
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                metric = _extract_metric_from_assign(node, path)
                if metric is not None:
                    metrics.append(metric)
    return sorted(metrics, key=lambda item: (item.metric_name, item.source, item.variable_name))


def render_metrics_markdown(metrics: list[MetricDefinition]) -> str:
    lines = [
        "# METRICS",
        "",
        "Generated from `core/` metric definitions by `scripts/generate_metrics_doc.py`.",
        "",
        "| Metric | Type | Labels | Description | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for metric in metrics:
        labels = ", ".join(metric.labels) if metric.labels else "-"
        description = metric.description.replace("|", "\\|")
        lines.append(
            f"| `{metric.metric_name}` | `{metric.metric_type}` | `{labels}` | "
            f"{description} | `{metric.source}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    args = parser.parse_args()

    rendered = render_metrics_markdown(collect_metrics(args.source_root))
    if args.check:
        if not args.output.exists():
            raise SystemExit(f"{args.output} is missing; run scripts/generate_metrics_doc.py")
        current = args.output.read_text(encoding="utf-8")
        if current != rendered:
            raise SystemExit(f"{args.output} is out of date; run scripts/generate_metrics_doc.py")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
