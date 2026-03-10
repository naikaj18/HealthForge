import os
from datetime import date
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "HealthForge")
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

METRICS = [
    "sleep_analysis",
    "step_count",
    "active_energy",
    "apple_exercise_time",
    "resting_heart_rate",
    "heart_rate_variability",
    "walking_heart_rate_average",
    "respiratory_rate",
    "workout",
]


def query_metric_range(
    user_id: str, metric: str, start_date: str, end_date: str
) -> list[dict]:
    """Query a single metric type for a date range using GSI1."""
    resp = table.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :pk AND GSI1SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}#METRIC#{metric}",
            ":start": start_date,
            ":end": end_date,
        },
    )
    return resp.get("Items", [])


def query_all_metrics_for_week(
    user_id: str, start: date, end: date
) -> dict[str, list[dict]]:
    """Query all metric types for a date range. Returns {metric_name: [items]}."""
    start_str = start.isoformat()
    end_str = end.isoformat()
    result = {}
    for metric in METRICS:
        items = query_metric_range(user_id, metric, start_str, end_str)
        if items:
            result[metric] = items
    return result


def decimal_to_float(obj):
    """Convert Decimals back to floats for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj
