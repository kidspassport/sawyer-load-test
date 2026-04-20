#!/usr/bin/env python3
"""Parse Locust results.csv and write a Markdown summary to stdout."""

import csv
import sys


def main():
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
    median = aggr["Median Response Time"]
    p95 = aggr["95%"]
    p99 = aggr["99%"]
    rps = aggr["Requests/s"]

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
    print(f"| Median (p50) | {median} ms |")
    print(f"| 95th Percentile | {p95} ms |")
    print(f"| 99th Percentile | {p99} ms |")

    if endpoints:
        print()
        print("### 📋 Per-Endpoint Breakdown")
        print()
        print("| Type | Endpoint | Requests | Failures | Median | p95 | p99 | RPS |")
        print("|------|----------|----------|----------|--------|-----|-----|-----|")
        for r in endpoints:
            ef = int(r["Failure Count"] or 0)
            flag = " ⚠️" if ef > 0 else ""
            reqs = int(r["Request Count"] or 0)
            print(
                f"| {r['Type']} | {r['Name']}{flag} | {reqs:,} | {ef:,} "
                f"| {r['Median Response Time']} ms | {r['95%']} ms "
                f"| {r['99%']} ms | {r['Requests/s']} |"
            )


if __name__ == "__main__":
    main()
