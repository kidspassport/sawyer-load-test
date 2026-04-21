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


def load_baseline(baselines, environment, scenario):
    """Return the baseline dict for the given env+scenario, or None."""
    if not baselines:
        return None
    return baselines.get(environment, {}).get(scenario)


def build_prompt(metadata, grafana, results_csv, stats_csv, baseline):
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

    if baseline:
        baseline_users = baseline.get("users")
        current_users = config.get("users")
        try:
            user_ratio = float(current_users) / float(baseline_users) if baseline_users and current_users else None
        except (ValueError, TypeError):
            user_ratio = None

        lines += [
            "## Established Baselines",
            f"- Baseline measured at: {baseline_users} users",
            f"- Current run: {current_users} users",
        ]
        if user_ratio is not None and abs(user_ratio - 1.0) > 0.1:
            lines.append(
                f"- Load difference: {user_ratio:.1f}x — latency thresholds below were established "
                f"at {baseline_users} users. Proportionally higher latency is expected at {current_users} users "
                "and should not be treated as a regression."
            )
        lines += [
            f"- p50 baseline: {baseline.get('p50_ms')} ms",
            f"- p95 baseline: {baseline.get('p95_ms')} ms",
            f"- p99 baseline: {baseline.get('p99_ms')} ms",
            f"- Failure rate baseline: {baseline.get('fail_rate_pct')}%",
            "",
            "Use these baselines to calibrate your assessment. "
            "Values within baseline are healthy — only flag latency or failure rate as a concern "
            "if it materially exceeds the baseline after accounting for any difference in user load.",
            "",
        ]
    else:
        lines += [
            "## Baselines",
            "No established baseline for this environment+scenario yet. "
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
        "--baselines",
        default="config/baselines.json",
        help="Path to baselines config (default: config/baselines.json)",
    )
    args = parser.parse_args()

    metadata = load_json("metadata.json")
    grafana = load_json("grafana-metrics.json")
    results_csv = load_file("results.csv")
    stats_csv = load_file("results_stats.csv")
    baselines = load_json(args.baselines)

    if not results_csv and not grafana:
        print("⚠️ No results data available for AI analysis", file=sys.stderr)
        sys.exit(0)

    env = (metadata or {}).get("environment", "unknown")
    scenario = (metadata or {}).get("scenario", "unknown")
    baseline = load_baseline(baselines, env, scenario)

    prompt = build_prompt(metadata, grafana, results_csv, stats_csv, baseline)

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


if __name__ == "__main__":
    main()
