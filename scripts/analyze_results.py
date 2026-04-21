#!/usr/bin/env python3
"""Analyze load test results using GitHub Models (GPT-4o-mini).

Reads results.csv, grafana-metrics.json, and metadata.json from the current
directory, sends a structured prompt to the GitHub Models API, and writes the
AI analysis as Markdown to stdout.

Usage:
    python3 scripts/analyze_results.py --token $GITHUB_TOKEN
"""

import argparse
import csv
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


def load_csv_summary(path):
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        aggr = next((r for r in rows if r["Name"] == "Aggregated"), None)
        endpoints = [r for r in rows if r["Name"] != "Aggregated"]
        return aggr, endpoints
    except FileNotFoundError:
        return None, []


def build_prompt(metadata, grafana, aggr, endpoints):
    env = metadata.get("environment", "unknown") if metadata else "unknown"
    scenario = metadata.get("scenario", "unknown") if metadata else "unknown"
    config = metadata.get("configuration", {}) if metadata else {}
    infra = metadata.get("infrastructure", {}) if metadata else {}

    lines = [
        "You are a performance engineering expert reviewing a load test report.",
        "Provide a concise analysis covering: overall health, latency assessment,",
        "throughput, any failures, and 2-3 specific actionable recommendations.",
        "Be direct and practical. Use Markdown formatting.",
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

    if aggr:
        total = int(aggr.get("Request Count") or 0)
        fails = int(aggr.get("Failure Count") or 0)
        fail_rate = (fails / total * 100) if total > 0 else 0
        lines += [
            "## Locust Results (client-side)",
            f"- Total requests: {total:,}",
            f"- Failures: {fails:,} ({fail_rate:.1f}%)",
            f"- Throughput: {aggr.get('Requests/s', 'N/A')} req/s",
            f"- Median latency: {aggr.get('Median Response Time', 'N/A')} ms",
            f"- p95 latency: {aggr.get('95%', 'N/A')} ms",
            f"- p99 latency: {aggr.get('99%', 'N/A')} ms",
            "",
        ]

        if endpoints:
            lines.append("### Endpoint breakdown")
            for r in endpoints[:15]:  # cap to avoid token limits
                ef = int(r.get("Failure Count") or 0)
                lines.append(
                    f"- {r['Type']} {r['Name']}: {r['Request Count']} reqs, "
                    f"{ef} failures, p50={r['Median Response Time']}ms, "
                    f"p95={r['95%']}ms, {r['Requests/s']} rps"
                )
            lines.append("")

    if grafana and grafana.get("p50_ms") is not None:
        source = grafana.get("source", "grafana")
        lines += [
            f"## Server-side Latency ({source})",
            f"- p50: {grafana.get('p50_ms')} ms",
            f"- p95: {grafana.get('p95_ms')} ms",
            f"- p99: {grafana.get('p99_ms')} ms",
            "",
        ]

    lines.append("Please analyze this load test and provide your assessment.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="GitHub token (GITHUB_TOKEN)")
    args = parser.parse_args()

    metadata = load_json("metadata.json")
    grafana = load_json("grafana-metrics.json")
    aggr, endpoints = load_csv_summary("results.csv")

    if not aggr and not grafana:
        print("⚠️ No results data available for AI analysis", file=sys.stderr)
        sys.exit(0)

    prompt = build_prompt(metadata, grafana, aggr, endpoints)

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
