#!/usr/bin/env python3
"""Fetch Nginx latency percentiles (p50/p95/p99) from Grafana Cloud Prometheus.

Uses a range query over the full test window and averages the resulting time
series — more robust than an instant query which can miss sparse scrape intervals.

Falls back to app-tier metrics (non-nginx) if nginx returns no data.

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

QUERY_TEMPLATES = {
    "nginx": {
        "p50_ms": "histogram_quantile(0.5, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name=~\".*nginx.*\"}}[{interval}s])))",
        "p95_ms": "histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name=~\".*nginx.*\"}}[{interval}s])))",
        "p99_ms": "histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name=~\".*nginx.*\"}}[{interval}s])))",
    },
    "app": {
        "p50_ms": "histogram_quantile(0.5, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name!~\".*nginx.*\"}}[{interval}s])))",
        "p95_ms": "histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name!~\".*nginx.*\"}}[{interval}s])))",
        "p99_ms": "histogram_quantile(0.99, sum(rate(traces_span_metrics_duration_seconds{{environment=\"{env}\", heroku_app_name!~\".*nginx.*\"}}[{interval}s])))",
    },
}


def query_grafana(token, queries, from_ms, to_ms, step_s):
    """POST a range query to Grafana and return the raw results dict."""
    payload = {
        "queries": queries,
        "from": str(from_ms),
        "to": str(to_ms),
    }
    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/ds/query",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR: Grafana API returned HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not reach Grafana: {e.reason}", file=sys.stderr)
        sys.exit(1)


def extract_average_ms(data, ref_id):
    """Average all values in a range query time series and convert s → ms."""
    try:
        values = data["results"][ref_id]["frames"][0]["data"]["values"][1]
        non_null = [v for v in values if v is not None]
        if not non_null:
            return None
        return round((sum(non_null) / len(non_null)) * 1000, 1)
    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return None


def build_queries(templates, env, interval_s, step_s):
    return [
        {
            "datasource": {"type": "prometheus", "uid": DATASOURCE_UID},
            "expr": tmpl.format(env=env, interval=interval_s),
            "range": True,
            "instant": False,
            "intervalMs": step_s * 1000,
            "refId": ref_id,
        }
        for ref_id, tmpl in templates.items()
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="Grafana service account token")
    parser.add_argument("--environment", required=True, help="e.g. sawyer-staging")
    parser.add_argument("--from-ms", required=True, type=int, help="Test start (Unix ms)")
    parser.add_argument("--to-ms", required=True, type=int, help="Test end (Unix ms)")
    parser.add_argument("--output", default="grafana-metrics.json", help="Output file path")
    args = parser.parse_args()

    duration_s = max((args.to_ms - args.from_ms) // 1000, 60)
    step_s = max(duration_s // 60, 15)  # ~60 data points, min 15s step

    print(f"Query window: {duration_s}s  rate_interval: {duration_s}s  step: {step_s}s", file=sys.stderr)

    # Try nginx first, fall back to app-tier if no data
    for source, templates in QUERY_TEMPLATES.items():
        queries = build_queries(templates, args.environment, duration_s, step_s)
        data = query_grafana(args.token, queries, args.from_ms, args.to_ms, step_s)

        results = {ref_id: extract_average_ms(data, ref_id) for ref_id in templates}

        if any(v is not None for v in results.values()):
            print(f"✓ Using {source} metrics", file=sys.stderr)
            break

        print(f"⚠️  No data from {source} metrics, trying next source...", file=sys.stderr)
    else:
        print("⚠️  All metric sources returned no data", file=sys.stderr)

    output = {
        "source": f"grafana-{source}",
        "environment": args.environment,
        "from_ms": args.from_ms,
        "to_ms": args.to_ms,
        **results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✓ Grafana latency ({source}): p50={results['p50_ms']}ms  p95={results['p95_ms']}ms  p99={results['p99_ms']}ms")


if __name__ == "__main__":
    main()

