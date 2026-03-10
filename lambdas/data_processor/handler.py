import json
import os
from datetime import datetime

import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

# Metrics we care about from Health Auto Export
SUPPORTED_METRICS = {
    "sleep_analysis",
    "step_count",
    "active_energy_burned",
    "apple_exercise_time",
    "resting_heart_rate",
    "heart_rate_variability",
    "walking_heart_rate_average",
    "workout",
    "vo2_max",
}


def parse_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from a datetime string."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: take first 10 chars
    return date_str[:10]


def build_item(user_id: str, metric_name: str, date: str, data_point: dict) -> dict:
    """Build a DynamoDB item from a single metric data point."""
    return {
        "PK": f"USER#{user_id}",
        "SK": f"METRIC#{metric_name}#{date}",
        "GSI1PK": f"USER#{user_id}#METRIC#{metric_name}",
        "GSI1SK": date,
        "metric": metric_name,
        "date": date,
        "data": data_point,
        "ingested_at": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """Process SQS messages: parse, deduplicate, write to DynamoDB."""
    records_written = 0
    records_skipped = 0

    for sqs_record in event["Records"]:
        message = json.loads(sqs_record["body"])
        user_id = message.get("user_id", "default")
        metrics = message.get("data", {}).get("metrics", [])

        for metric in metrics:
            metric_name = metric.get("name", "").lower().replace(" ", "_")

            if metric_name not in SUPPORTED_METRICS:
                continue

            data_points = metric.get("data", [])
            for data_point in data_points:
                date_str = data_point.get("date", "")
                if not date_str:
                    continue

                date = parse_date(date_str)
                item = build_item(user_id, metric_name, date, data_point)

                # Conditional put — skip if already exists (deduplication)
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
