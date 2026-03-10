import json
import os
from datetime import datetime
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

# Metrics we care about from Health Auto Export
# Maps possible names from the export to our canonical names
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
}


def parse_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from a datetime string.

    Handles formats like:
    - '2026-03-08 00:00:00 -0800'
    - '2026-03-08 23:15:00'
    - '2026-03-08'
    - '2026-03-08T23:15:00Z'
    """
    # Strip timezone offset like ' -0800' or ' +0000'
    clean = date_str.strip()
    for sep in (" -", " +"):
        idx = clean.rfind(sep)
        # Only strip if it looks like a timezone (at the end, 4-5 digits)
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
    """Convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats(i) for i in obj]
    return obj


def build_item(user_id: str, metric_name: str, date: str, data_point: dict) -> dict:
    """Build a DynamoDB item from a single metric data point."""
    return {
        "PK": f"USER#{user_id}",
        "SK": f"METRIC#{metric_name}#{date}",
        "GSI1PK": f"USER#{user_id}#METRIC#{metric_name}",
        "GSI1SK": date,
        "metric": metric_name,
        "date": date,
        "data": convert_floats(data_point),
        "ingested_at": datetime.utcnow().isoformat(),
    }


def slim_workout(workout: dict) -> dict:
    """Extract only essential fields from workout (raw data can exceed 400KB)."""
    slim = {
        "name": workout.get("name", "unknown"),
        "start": workout.get("start", ""),
        "end": workout.get("end", ""),
        "duration": workout.get("duration", 0),
        "totalEnergyBurned": workout.get("totalEnergyBurned", 0),
        "activeEnergyBurned": workout.get("activeEnergyBurned", 0),
        "isIndoor": workout.get("isIndoor", False),
    }
    if "avgHeartRate" in workout:
        slim["avgHeartRate"] = workout["avgHeartRate"]
    if "heartRate" in workout:
        slim["heartRateSummary"] = {
            "min": workout["heartRate"].get("min"),
            "avg": workout["heartRate"].get("avg"),
            "max": workout["heartRate"].get("max"),
        }
    if "totalDistance" in workout:
        slim["totalDistance"] = workout["totalDistance"]
    return slim


def build_workout_item(user_id: str, date: str, workout: dict) -> dict:
    """Build a DynamoDB item from a workout entry."""
    return {
        "PK": f"USER#{user_id}",
        "SK": f"METRIC#workout#{date}#{workout.get('name', 'unknown')}",
        "GSI1PK": f"USER#{user_id}#METRIC#workout",
        "GSI1SK": date,
        "metric": "workout",
        "date": date,
        "data": convert_floats(slim_workout(workout)),
        "ingested_at": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """Process SQS messages: parse, deduplicate, write to DynamoDB."""
    records_written = 0
    records_skipped = 0

    for sqs_record in event["Records"]:
        message = json.loads(sqs_record["body"])
        user_id = message.get("user_id", "default")
        payload = message.get("data", {})

        # Process metrics
        metrics = payload.get("metrics", [])
        for metric in metrics:
            raw_name = metric.get("name", "").lower().replace(" ", "_")
            metric_name = METRIC_ALIASES.get(raw_name)

            if metric_name is None:
                continue

            data_points = metric.get("data", [])
            for data_point in data_points:
                date_str = data_point.get("date", "")
                if not date_str:
                    continue

                date = parse_date(date_str)
                item = build_item(user_id, metric_name, date, data_point)

                try:
                    table.put_item(
                        Item=item,
                        ConditionExpression="attribute_not_exists(PK)",
                    )
                    records_written += 1
                except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                    records_skipped += 1

        # Process workouts (separate array in Health Auto Export)
        workouts = payload.get("workouts", [])
        for workout in workouts:
            date_str = workout.get("start", workout.get("date", ""))
            if not date_str:
                continue

            date = parse_date(date_str)
            item = build_workout_item(user_id, date, workout)

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(PK)",
                )
                records_written += 1
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                records_skipped += 1

    return {
        "written": records_written,
        "skipped": records_skipped,
    }
