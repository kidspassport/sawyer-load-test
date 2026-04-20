#!/usr/bin/env python3
"""Fetch Nginx latency percentiles (p50/p95/p99) from Grafana Cloud Prometheus.

Writes a JSON file like:
  {"p50_ms": 320.5, "p95_ms": 681.0, "p99_ms": 1680.2,
   "source": "grafana-nginx", "environment": "sawyer-staging"}
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

GRAFANA_URL = "https://daysmartsawyer.grafana.net"
DATASOURCE_UID = "grafanacloud-prom"

# Nginx latency queries — $__rate_interval replaced at runtime with actual test duration
QUERIES = {
    "p50_ms": (
        "histogram_quantile(0.5, sum(rate("
        "traces_span_metrics_duration_seconds{{"
        'environment="{env}", heroku_app_name=~".*nginx.*"'
        "}}[{interval}s])))"
    ),
    "p95_ms": (
        "histogram_quantile(0.95, sum(rate("
        "traces_span_metrics_duration_seconds{{"
        'environment="{env}", heroku_app_name=~".*nginx.*"'
        "}}[{interval}s])))"
    ),
    "p99_ms": (
        "histogram_quantile(0.99, sum(rate("
        "traces_span_metrics_duration_seconds{{"
        'environment="{env}", heroku_app_name=~".*nginx.*"'
        "}}[{interval}s])))"
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="Grafana service account token")
    parser.add_argument("--environment", required=True, help="e.g. sawyer-staging")
    parser.add_argument("--from-ms", required=True, type=int, help="Test start (Unix ms)")
    parser.add_argument("--to-ms", required=True, type=int, help="Test end (Unix ms)")
    parser.add_argument("--output", default="grafana-metrics.json", help="Output file path")
    args = parser.parse_args()

    # Use actual test duration as the Prometheus rate interval (min 60s)
    duration_s = max((args.to_ms - args.from_ms) // 1000, 60)

    queries = [
        {
            "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
            "expr": tmpl.format(env=args.environment, interval=duration_s),
            "instant": True,
            "refId": ref_id,
        }
        for ref_id, tmpl in QUERIES.items()
    ]

    payload = {
        "queries": queries,
        "from": str(args.from_ms),
        "to": str(args.to_ms),
    }

    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/ds/query",
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
        print(f"ERROR: Grafana API returned HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not reach Grafana: {e.reason}", file=sys.stderr)
        sys.exit(1)

    results = {"source": "grafana-nginx", "environment": args.environment,
               "from_ms": args.from_ms, "to_ms": args.to_ms}

    for ref_id in QUERIES:
        try:
            # instant query → one frame, values = [[timestamps...], [values...]]
            value = data["results"][ref_id]["frames"][0]["data"]["values"][1][0]
            # metric is in seconds — convert to ms
            results[ref_id] = round(value * 1000, 1) if value is not None else None
        except (KeyError, IndexError, TypeError):
            results[ref_id] = None

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    p50, p95, p99 = results["p50_ms"], results["p95_ms"], results["p99_ms"]
    print(f"✓ Grafana Nginx latency: p50={p50}ms  p95={p95}ms  p99={p99}ms")


if __name__ == "__main__":
    main()
