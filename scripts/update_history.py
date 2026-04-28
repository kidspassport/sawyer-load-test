#!/usr/bin/env python3
"""Append this run's metrics to baselines/history.json in S3.

Downloads the existing history, appends a new entry for this run,
then uploads it back. Creates the file if it doesn't exist yet.

Usage:
    python3 scripts/update_history.py --bucket sawyer-load-test-results
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile


def s3_download(bucket, key, dest):
    """Return True if downloaded, False if key doesn't exist."""
    result = subprocess.run(
        ["aws", "s3", "cp", f"s3://{bucket}/{key}", dest],
        capture_output=True,
    )
    return result.returncode == 0


def s3_upload(src, bucket, key):
    result = subprocess.run(
        ["aws", "s3", "cp", src, f"s3://{bucket}/{key}"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR: S3 upload failed: {result.stderr.decode()}", file=sys.stderr)
        sys.exit(1)


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default="sawyer-load-test-results")
    args = parser.parse_args()

    S3_KEY = "baselines/history.json"

    metadata  = load_json("metadata.json")
    grafana   = load_json("grafana-metrics.json")

    if not metadata:
        print("⚠️  metadata.json not found — skipping history update", file=sys.stderr)
        sys.exit(0)

    # Build entry for this run
    config = metadata.get("configuration", {})
    infra  = metadata.get("infrastructure", {})

    # Pull failure rate from results.csv if available
    fail_rate = None
    try:
        import csv
        with open("results.csv", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("Name") == "Aggregated":
                    total = int(row["Request Count"] or 0)
                    fails = int(row["Failure Count"] or 0)
                    fail_rate = round((fails / total * 100), 2) if total > 0 else 0.0
                    break
    except FileNotFoundError:
        pass

    entry = {
        "run_id":        metadata.get("test_run_id"),
        "timestamp":     metadata.get("timestamp"),
        "environment":   metadata.get("environment"),
        "scenario":      metadata.get("scenario"),
        "users":         config.get("users"),
        "spawn_rate":    config.get("spawn_rate"),
        "duration_minutes": config.get("duration_minutes"),
        "dynos":         infra.get("dynos"),
        "aurora_acu":    infra.get("aurora_acu"),
        "fail_rate_pct": fail_rate,
        "workflow_url":  metadata.get("github", {}).get("workflow_url"),
    }

    # Add Grafana latency if available
    if grafana and grafana.get("p50_ms") is not None:
        entry["latency_source"] = grafana.get("source")
        entry["p50_ms"]  = grafana.get("p50_ms")
        entry["p95_ms"]  = grafana.get("p95_ms")
        entry["p99_ms"]  = grafana.get("p99_ms")

    # Download existing history (or start fresh)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    history = []
    if s3_download(args.bucket, S3_KEY, tmp_path):
        history = load_json(tmp_path) or []
        print(f"✓ Loaded {len(history)} existing history entries")
    else:
        print("✓ No existing history — creating new file")

    history.append(entry)

    with open(tmp_path, "w") as f:
        json.dump(history, f, indent=2)

    s3_upload(tmp_path, args.bucket, S3_KEY)
    os.unlink(tmp_path)

    print(f"✓ History updated ({len(history)} total entries) → s3://{args.bucket}/{S3_KEY}")

    # Write path to local file so analyze_results.py can read it directly
    with open("history.json", "w") as f:
        json.dump(history, f)


if __name__ == "__main__":
    main()
