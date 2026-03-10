import json
import os
import boto3

sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]


def lambda_handler(event, context):
    """Receive health data from Health Auto Export and push to SQS."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    # Validate: must have data.metrics
    if "data" not in body or "metrics" not in body.get("data", {}):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing data.metrics"}),
        }

    metrics = body["data"]["metrics"]
    if not isinstance(metrics, list) or len(metrics) == 0:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "metrics must be a non-empty list"}),
        }

    # For now, single user — hardcode user ID
    message = {
        "user_id": "default",
        "data": body["data"],
    }

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message),
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "received", "metrics_count": len(metrics)}),
    }
