#!/usr/bin/env python3
"""Analyze load test results using GitHub Models (GPT-4o-mini).

Reads results.csv, grafana-metrics.json, and metadata.json from the current
directory, sends a structured prompt to the GitHub Models API, and writes the
AI analysis as Markdown to stdout.

Usage:
    python3 scripts/analyze_results.py --token $GITHUB_TOKEN
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o-mini"


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


def compute_history_stats(history, environment, scenario, current_users):
    """Return stats dict from prior matching runs, or None if too few runs."""
    if not history:
        return None

    # Match on env + scenario; group by similar user count (within 20%)
    try:
        cu = float(current_users)
    except (TypeError, ValueError):
        cu = None

    runs = []
    for r in history:
        if r.get("environment") != environment or r.get("scenario") != scenario:
            continue
        if r.get("p50_ms") is None:  # skip runs without latency data
            continue
        if cu is not None:
            try:
                ratio = float(r["users"]) / cu
                if not (0.8 <= ratio <= 1.2):
                    continue
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        runs.append(r)

    if not runs:
        return None

    def avg(key):
        vals = [r[key] for r in runs if r.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "run_count": len(runs),
        "avg_p50_ms": avg("p50_ms"),
        "avg_p95_ms": avg("p95_ms"),
        "avg_p99_ms": avg("p99_ms"),
        "avg_fail_rate_pct": avg("fail_rate_pct"),
        "recent_runs": sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)[:5],
    }


def build_prompt(metadata, grafana, results_csv, stats_csv, history_stats):
    env = metadata.get("environment", "unknown") if metadata else "unknown"
    scenario = metadata.get("scenario", "unknown") if metadata else "unknown"
    config = metadata.get("configuration", {}) if metadata else {}
    infra = metadata.get("infrastructure", {}) if metadata else {}

    lines = [
        "You are a performance engineering expert reviewing a load test report.",
        "Format your response using exactly these three sections:",
        "",
        "## 📋 Load Test Summary",
        "One short paragraph covering: environment, scenario, duration, user count,",
        "dyno/ACU settings, and whether the test completed successfully without major errors or regressions.",
        "",
        "## 🔍 Key Findings",
        "3-5 bullet points. Each should be a single sentence.",
        "Compare to baseline if provided. Lead with the most important finding.",
        "",
        "## 📊 Detailed Analysis",
        "Deeper breakdown of latency, throughput, failures, and infrastructure behaviour.",
        "End with 2-3 specific, actionable recommendations.",
        "",
        "Be direct and practical. Do not pad with generic advice.",
        "",
        "## Test Configuration",
        f"- Environment: {env}",
        f"- Scenario: {scenario}",
        f"- Users: {config.get('users', 'unknown')}",
        f"- Spawn rate: {config.get('spawn_rate', 'unknown')}/s",
        f"- Duration: {config.get('duration_minutes', 'unknown')} minutes",
        f"- Dynos: {infra.get('dynos', 'unknown')}",
        f"- Aurora ACUs: {infra.get('aurora_acu', 'unknown')}",
        "",
    ]

    if history_stats:
        n = history_stats["run_count"]
        lines += [
            f"## Historical Baselines (averaged from {n} prior runs with similar user load)",
            f"- avg p50: {history_stats['avg_p50_ms']} ms",
            f"- avg p95: {history_stats['avg_p95_ms']} ms",
            f"- avg p99: {history_stats['avg_p99_ms']} ms",
            f"- avg failure rate: {history_stats['avg_fail_rate_pct']}%",
            "",
        ]
        recent = history_stats["recent_runs"]
        if recent:
            lines.append("Recent runs (most recent first):")
            for r in recent:
                lines.append(
                    f"- {r.get('timestamp', 'unknown')[:10]}  "
                    f"{r.get('users')} users  "
                    f"p50={r.get('p50_ms')}ms  p95={r.get('p95_ms')}ms  p99={r.get('p99_ms')}ms  "
                    f"failures={r.get('fail_rate_pct')}%"
                )
        lines += [
            "",
            "Use these historical averages to calibrate your assessment. "
            "Only flag latency or failure rate as a concern if it materially exceeds the historical average. "
            "Runs were filtered to similar user counts (within 20%) so load differences are already accounted for.",
            "",
        ]
    else:
        lines += [
            "## Historical Baselines",
            "No prior runs with matching environment, scenario, and similar user count. "
            "Assess on general web application performance standards.",
            "",
        ]

    if grafana and grafana.get("p50_ms") is not None:
        source = grafana.get("source", "grafana")
        lines += [
            f"## Server-side Latency ({source})",
            f"- p50: {grafana.get('p50_ms')} ms",
            f"- p95: {grafana.get('p95_ms')} ms",
            f"- p99: {grafana.get('p99_ms')} ms",
            "",
        ]

    if results_csv:
        lines += [
            "## Locust Results (results.csv)",
            "```",
            results_csv.strip(),
            "```",
            "",
        ]

    if stats_csv:
        lines += [
            "## Locust Full History (results_stats.csv)",
            "```",
            stats_csv.strip(),
            "```",
            "",
        ]

    lines.append("Please analyze this load test and provide your assessment.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="GitHub token (GITHUB_TOKEN)")
    parser.add_argument(
        "--history",
        default="history.json",
        help="Path to run history JSON (default: history.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Also write AI analysis to this file (in addition to stdout)",
    )
    args = parser.parse_args()

    metadata = load_json("metadata.json")
    grafana = load_json("grafana-metrics.json")
    results_csv = load_file("results.csv")
    stats_csv = load_file("results_stats.csv")
    history = load_json(args.history)

    if not results_csv and not grafana:
        print("⚠️ No results data available for AI analysis", file=sys.stderr)
        sys.exit(0)

    env = (metadata or {}).get("environment", "unknown")
    scenario = (metadata or {}).get("scenario", "unknown")
    current_users = (metadata or {}).get("configuration", {}).get("users")
    history_stats = compute_history_stats(history, env, scenario, current_users)

    prompt = build_prompt(metadata, grafana, results_csv, stats_csv, history_stats)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    req = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {args.token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"⚠️ GitHub Models API error (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"⚠️ Could not reach GitHub Models API: {e.reason}", file=sys.stderr)
        sys.exit(1)

    analysis = data["choices"][0]["message"]["content"]
    print(analysis)
    if args.output:
        with open(args.output, "w") as f:
            f.write(analysis)


if __name__ == "__main__":
    main()
