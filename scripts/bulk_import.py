"""
Bulk import Health Auto Export JSON file directly into DynamoDB.

Usage:
    python scripts/bulk_import.py /path/to/HealthAutoExport.json

This bypasses API Gateway/SQS and writes directly to DynamoDB,
which is necessary for large export files (>256KB).
"""

import json
import os
import sys

# Ensure project root is on the path so we can import from lambdas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3

from lambdas.data_processor.handler import (
    METRIC_ALIASES,
    build_item,
    build_workout_item,
    parse_date,
)

TABLE_NAME = "HealthForge"
REGION = "us-east-1"
USER_ID = "default"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/bulk_import.py <path-to-json>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Loading {filepath}...")

    with open(filepath) as f:
        data = json.load(f)

    payload = data.get("data", data)
    written = 0
    skipped = 0

    # Process metrics
    metrics = payload.get("metrics", [])
    for metric in metrics:
        raw_name = metric.get("name", "").lower().replace(" ", "_")
        metric_name = METRIC_ALIASES.get(raw_name)

        if metric_name is None:
            continue

        data_points = metric.get("data", [])
        for dp in data_points:
            date_str = dp.get("date", "")
            if not date_str:
                continue

            date = parse_date(date_str)
            item = build_item(USER_ID, metric_name, date, dp)

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(PK)",
                )
                written += 1
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                skipped += 1

        print(f"  {metric_name}: {len(data_points)} points")

    # Process workouts
    workouts = payload.get("workouts", [])
    for workout in workouts:
        date_str = workout.get("start", workout.get("date", ""))
        if not date_str:
            continue

        date = parse_date(date_str)
        item = build_workout_item(USER_ID, date, workout)

        try:
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK)",
            )
            written += 1
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            skipped += 1

    print(f"  workouts: {len(workouts)} entries")
    print(f"\nDone! Written: {written}, Skipped (duplicates): {skipped}")


if __name__ == "__main__":
    main()
