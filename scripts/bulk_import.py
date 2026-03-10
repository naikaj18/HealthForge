"""
Bulk import Health Auto Export JSON file directly into DynamoDB.

Usage:
    python scripts/bulk_import.py /path/to/HealthAutoExport.json

This bypasses API Gateway/SQS and writes directly to DynamoDB,
which is necessary for large export files (>256KB).
"""

import json
import sys
from datetime import datetime
from decimal import Decimal

import boto3

TABLE_NAME = "HealthForge"
REGION = "us-east-1"
USER_ID = "default"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

METRIC_ALIASES = {
    "sleep_analysis": "sleep_analysis",
    "step_count": "step_count",
    "active_energy": "active_energy",
    "active_energy_burned": "active_energy",
    "apple_exercise_time": "apple_exercise_time",
    "resting_heart_rate": "resting_heart_rate",
    "heart_rate_variability": "heart_rate_variability",
    "walking_heart_rate_average": "walking_heart_rate_average",
    "vo2_max": "vo2_max",
    "respiratory_rate": "respiratory_rate",
}


def parse_date(date_str: str) -> str:
    clean = date_str.strip()
    for sep in (" -", " +"):
        idx = clean.rfind(sep)
        if idx > 10:
            tz_part = clean[idx + 2:]
            if tz_part.isdigit() and len(tz_part) in (4, 5):
                clean = clean[:idx]
                break

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10]


def convert_floats(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats(i) for i in obj]
    return obj


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
            item = {
                "PK": f"USER#{USER_ID}",
                "SK": f"METRIC#{metric_name}#{date}",
                "GSI1PK": f"USER#{USER_ID}#METRIC#{metric_name}",
                "GSI1SK": date,
                "metric": metric_name,
                "date": date,
                "data": convert_floats(dp),
                "ingested_at": datetime.utcnow().isoformat(),
            }

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(PK)",
                )
                written += 1
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                skipped += 1

        print(f"  {metric_name}: {len(data_points)} points")

    # Process workouts — only keep essential fields to stay under 400KB limit
    workouts = payload.get("workouts", [])
    for workout in workouts:
        date_str = workout.get("start", workout.get("date", ""))
        if not date_str:
            continue

        date = parse_date(date_str)
        workout_name = workout.get("name", "unknown")

        # Extract only the fields we need (raw workout data can be huge)
        slim_workout = {
            "name": workout_name,
            "start": workout.get("start", ""),
            "end": workout.get("end", ""),
            "duration": workout.get("duration", 0),
            "totalEnergyBurned": workout.get("totalEnergyBurned", 0),
            "activeEnergyBurned": workout.get("activeEnergyBurned", 0),
            "isIndoor": workout.get("isIndoor", False),
        }
        if "avgHeartRate" in workout:
            slim_workout["avgHeartRate"] = workout["avgHeartRate"]
        if "heartRate" in workout:
            slim_workout["heartRateSummary"] = {
                "min": workout["heartRate"].get("min"),
                "avg": workout["heartRate"].get("avg"),
                "max": workout["heartRate"].get("max"),
            }
        if "totalDistance" in workout:
            slim_workout["totalDistance"] = workout["totalDistance"]

        item = {
            "PK": f"USER#{USER_ID}",
            "SK": f"METRIC#workout#{date}#{workout_name}",
            "GSI1PK": f"USER#{USER_ID}#METRIC#workout",
            "GSI1SK": date,
            "metric": "workout",
            "date": date,
            "data": convert_floats(slim_workout),
            "ingested_at": datetime.utcnow().isoformat(),
        }

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
