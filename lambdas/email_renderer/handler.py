import json
import os

import boto3

# Import templates
import sys
sys.path.insert(0, os.path.dirname(__file__))
from templates import render_full_email

ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")


def lambda_handler(event, context):
    """Step Functions entry point. Renders email and sends via SES."""
    if not event.get("send_email", True):
        return {"status": "skipped", "reason": event.get("skip_reason", "No data")}

    subject, html_body, text_body = render_full_email(event, prior_week=None)

    if not SENDER_EMAIL or not RECIPIENT_EMAIL:
        # Local testing mode — just return the email
        return {"status": "rendered", "subject": subject, "body": html_body}

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": text_body, "Charset": "UTF-8"},
            },
        },
    )

    return {"status": "sent", "subject": subject}
