# scripts/test_email_local.py
"""Run the full aggregation pipeline locally and print the email.

Usage: PYTHONPATH=. python scripts/test_email_local.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "email_renderer"))

os.environ.setdefault("TABLE_NAME", "HealthForge")
os.environ.setdefault("AWS_REGION", "us-east-1")

from lambdas.aggregation.handler import aggregate_week
from lambdas.email_renderer.templates import render_full_email
from datetime import date


def main():
    ref_date = date.today()
    if len(sys.argv) > 1:
        ref_date = date.fromisoformat(sys.argv[1])

    print(f"Aggregating week for reference date: {ref_date}")
    print()

    data = aggregate_week("default", ref_date)

    # Add placeholder insights (no Gemini in local mode)
    data["insights"] = {
        "sleep_insight": "Local test — Gemini insight would appear here.",
        "weekly_focus": "Local test — weekly focus would appear here.",
    }
    data["send_email"] = True
    data["limited_data"] = False

    subject, body = render_full_email(data)

    print(f"Subject: {subject}")
    print()
    print(body)

    # Also dump raw data for debugging
    with open("/tmp/healthforge_aggregation.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nRaw data saved to /tmp/healthforge_aggregation.json")


if __name__ == "__main__":
    main()
