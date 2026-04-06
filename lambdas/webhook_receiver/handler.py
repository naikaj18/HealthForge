import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]


def lambda_handler(event, context):
    """Receive health data from Health Auto Export and push to SQS."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    # Validate: must have data.metrics or data.workouts
    data = body.get("data", {})
    if "data" not in body:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing data"}),
        }

    metrics = data.get("metrics", [])
    workouts = data.get("workouts", [])

    # Log sample of step_count metric to understand data shape
    for m in metrics:
        if m.get("name", "").lower() == "step_count":
            sample = m.get("data", [])[:3]
            logger.info(f"step_count metric: {len(m.get('data', []))} data points, sample: {json.dumps(sample)}")

    if not metrics and not workouts:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing data.metrics or data.workouts"}),
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
        "body": json.dumps({
            "status": "received",
            "metrics_count": len(metrics),
            "workouts_count": len(workouts),
        }),
    }
