#!/usr/bin/env python3
"""Parse Locust results.csv and write a Markdown summary to stdout.

Optionally accepts Grafana Nginx latency metrics via --grafana-metrics to
replace Locust's latency values (which measure client-side timing) with
server-side Nginx latency from Prometheus traces.
"""

import argparse
import csv
import json
import sys


def load_grafana_metrics(path):
    """Return (p50, p95, p99) in ms as strings, or None if unavailable."""
    try:
        with open(path) as f:
            data = json.load(f)
        p50 = data.get("p50_ms")
        p95 = data.get("p95_ms")
        p99 = data.get("p99_ms")
        if all(v is not None for v in (p50, p95, p99)):
            return str(p50), str(p95), str(p99)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grafana-metrics",
        metavar="FILE",
        help="Path to grafana-metrics.json (from fetch_grafana_metrics.py). "
             "When provided, Nginx p50/p95/p99 from Grafana replace Locust latency.",
    )
    args = parser.parse_args()

    try:
        with open("results.csv", newline="") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print("⚠️ results.csv not found")
        sys.exit(0)

    aggr = next((r for r in rows if r["Name"] == "Aggregated"), None)
    endpoints = [r for r in rows if r["Name"] != "Aggregated"]

    if not aggr:
        print("⚠️ Could not find Aggregated row in results CSV")
        sys.exit(0)

    total = int(aggr["Request Count"] or 0)
    fails = int(aggr["Failure Count"] or 0)
    fail_rate = (fails / total * 100) if total > 0 else 0
    rps = aggr["Requests/s"]

    # Latency: prefer Grafana Nginx metrics, fall back to Locust client-side
    grafana = load_grafana_metrics(args.grafana_metrics) if args.grafana_metrics else None
    if grafana:
        median, p95, p99 = grafana
        latency_source = "Nginx/Grafana"
    else:
        median = aggr["Median Response Time"]
        p95 = aggr["95%"]
        p99 = aggr["99%"]
        latency_source = "Locust"

    if fails == 0:
        status = "✅ All requests succeeded"
    elif fail_rate < 1:
        status = f"⚠️ Low failure rate ({fail_rate:.1f}%)"
    else:
        status = f"❌ High failure rate ({fail_rate:.1f}%) — investigation needed"

    print(f"### {status}")
    print()
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Total Requests | {total:,} |")
    print(f"| Failures | {fails:,} ({fail_rate:.1f}%) |")
    print(f"| Throughput | {rps} req/s |")
    print(f"| Median (p50) _{latency_source}_ | {median} ms |")
    print(f"| 95th Percentile _{latency_source}_ | {p95} ms |")
    print(f"| 99th Percentile _{latency_source}_ | {p99} ms |")


if __name__ == "__main__":
    main()
