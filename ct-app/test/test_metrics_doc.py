from pathlib import Path

from scripts.generate_metrics_doc import collect_metrics, render_metrics_markdown


def test_collect_metrics_finds_known_metric_definitions():
    metrics = collect_metrics()
    names = {metric.metric_name for metric in metrics}

    assert "ct_messages_processed_total" in names
    assert "ct_channel_operation" in names
    assert "ct_peer_delay" in names


def test_render_metrics_markdown_includes_table_and_labels(tmp_path: Path):
    rendered = render_metrics_markdown(collect_metrics())

    assert "| Metric | Type | Labels | Description | Source |" in rendered
    assert "`ct_session_operation`" in rendered
    assert "relayer, op, success" in rendered
