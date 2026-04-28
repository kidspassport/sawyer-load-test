#!/usr/bin/env python3
"""Assemble a Markdown load test report from artifacts in the current directory.

Combines test configuration (metadata.json), the metrics table
(parse_locust_results.py), Grafana panel images (public S3 URLs), and the
AI analysis (ai-analysis.md) into a single Notion-importable Markdown file.

Usage:
    python3 scripts/generate_report.py \
        --run-id staging-place_order-run42 \
        --base-url https://sawyer-load-test-results.s3.amazonaws.com/results/2026-04-24/staging-place_order-run42 \
        --workflow-url https://github.com/org/repo/actions/runs/12345 \
        --output load-test-report.md
"""

import argparse
import json
import os
import subprocess
import sys


def read(path):
    try:
        return open(path).read()
    except FileNotFoundError:
        return None


def load_json(path):
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--base-url", required=True, help="Public S3 base URL for this run's folder")
    parser.add_argument("--workflow-url", required=True)
    parser.add_argument("--output", default="load-test-report.md")
    args = parser.parse_args()

    metadata  = load_json("metadata.json") or {}
    config    = metadata.get("configuration", {})
    infra     = metadata.get("infrastructure", {})
    timestamp = metadata.get("timestamp", "")
    environment = metadata.get("environment", "unknown")
    scenario    = metadata.get("scenario", "unknown")

    lines = [
        f"# Load Test Report: {scenario} / {environment}",
        "",
        f"**Date:** {timestamp[:10] if timestamp else 'unknown'}  ",
        f"**Run:** [{args.run_id}]({args.workflow_url})  ",
        f"**Environment:** {environment}  ",
        f"**Scenario:** {scenario}  ",
        "",
        "## Configuration",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Users | {config.get('users', '—')} |",
        f"| Spawn Rate | {config.get('spawn_rate', '—')} |",
        f"| Duration | {config.get('duration_minutes', '—')} min |",
        f"| Dynos | {infra.get('dynos', '—')} |",
        f"| Aurora ACU | {infra.get('aurora_acu', '—')} |",
        f"| Host | {config.get('host', '—')} |",
        "",
    ]

    # Metrics table from parse_locust_results.py
    metrics_cmd = ["python3", "scripts/parse_locust_results.py"]
    if os.path.exists("grafana-metrics.json"):
        metrics_cmd += ["--grafana-metrics", "grafana-metrics.json"]
    result = subprocess.run(metrics_cmd, capture_output=True, text=True)
    if result.stdout.strip():
        lines += ["## Metrics Summary", "", result.stdout.strip(), ""]

    # Grafana panel images (inline, public S3 URLs)
    panels = [
        ("grafana-panel-throughput.png",  "Throughput"),
        ("grafana-panel-latency-ts.png",  "Latency (time series)"),
        ("grafana-panel-latency-pct.png", "Latency Percentiles (p50 / p95 / p99)"),
        ("grafana-panel-cpu.png",         "CPU Usage"),
    ]
    panel_lines = []
    for fname, label in panels:
        if os.path.exists(fname):
            url = f"{args.base_url}/{fname}"
            panel_lines += [f"### {label}", "", f"![{label}]({url})", ""]
    if panel_lines:
        lines += ["## Grafana Panels", ""] + panel_lines

    # AI analysis
    ai = read("ai-analysis.md")
    if ai and ai.strip():
        lines += ["## AI Analysis", "", ai.strip(), ""]

    report = "\n".join(lines)
    with open(args.output, "w") as f:
        f.write(report)
    print(f"✓ Report generated: {args.output} ({len(report)} chars)")


if __name__ == "__main__":
    main()
