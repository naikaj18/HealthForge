# lambdas/insight/handler.py
import json
import os
import urllib.request
import urllib.error

GEMINI_API_KEY_PARAM = os.environ.get("GEMINI_API_KEY_PARAM", "/healthforge/gemini-api-key")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

_cached_api_key = None


def _get_api_key() -> str:
    """Fetch Gemini API key from SSM (cached after first call)."""
    global _cached_api_key
    if _cached_api_key is not None:
        return _cached_api_key
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        resp = ssm.get_parameter(Name=GEMINI_API_KEY_PARAM, WithDecryption=True)
        _cached_api_key = resp["Parameter"]["Value"]
    except Exception:
        _cached_api_key = os.environ.get("GEMINI_API_KEY", "")
    return _cached_api_key


def call_gemini(prompt: str) -> str:
    """Call Gemini Flash API. Returns generated text or fallback."""
    api_key = _get_api_key()
    if not api_key:
        return ""

    url = f"{GEMINI_URL}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.7},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
        return ""


def generate_sleep_insight(data: dict) -> str:
    """Generate a 1-2 line sleep insight."""
    sleep = data.get("sleep", {})
    details = sleep.get("details", {})

    prompt = f"""You are a personal health analyst. Write a 1-2 line insight about this person's sleep this week. Be specific, cite their numbers, and be encouraging but honest.

Sleep score: {sleep.get('avg_score')} (avg of {sleep.get('nights_tracked')} nights)
Avg total sleep: {details.get('avg_total_sleep')} hours
Avg deep sleep: {details.get('avg_deep')} hours
Avg efficiency: {details.get('avg_efficiency')}%
Best night: {details.get('best_night')}
Worst night: {details.get('worst_night')}

Keep it under 50 words. No greetings or sign-offs. Just the insight."""

    result = call_gemini(prompt)
    if not result:
        # Template fallback
        avg = sleep.get("avg_score", 0)
        if avg >= 80:
            return "Strong sleep week. Keep up the consistency."
        elif avg >= 60:
            return f"Decent sleep this week at {avg}. Check your worst night for clues on what to improve."
        else:
            return f"Tough sleep week at {avg}. Focus on bedtime consistency — it's the easiest lever."
    return result


def generate_weekly_focus(data: dict) -> str:
    """Generate a 3-4 line actionable focus for next week."""
    scores = {
        "Sleep": data.get("sleep", {}).get("avg_score"),
        "Fitness": data.get("fitness", {}).get("score"),
        "Recovery": data.get("recovery", {}).get("avg_score"),
        "Consistency": data.get("consistency", {}).get("score"),
        "Cardio": data.get("cardio", {}).get("score"),
    }

    # Find weakest area
    valid = {k: v for k, v in scores.items() if v is not None}
    weakest = min(valid, key=valid.get) if valid else "Sleep"

    anomalies = data.get("anomalies", [])
    correlations = data.get("correlations", {})

    prompt = f"""You are a personal health analyst. Based on this week's data, suggest ONE specific, actionable thing to focus on next week.

Scores: {json.dumps(valid)}
Weakest area: {weakest} ({valid.get(weakest)})
Anomalies: {json.dumps(anomalies) if anomalies else 'None'}
Correlations found: {json.dumps(correlations) if correlations else 'Still building baseline'}
Consistency details: bedtime std {data.get('consistency', {}).get('bedtime_std_min', '?')} min, sleep range {data.get('consistency', {}).get('sleep_range_hours', '?')} hours

Be specific. Cite their numbers. Keep it under 80 words. No greetings. Format as 3-4 short lines."""

    result = call_gemini(prompt)
    if not result:
        score = valid.get(weakest, 0)
        return f"Your biggest opportunity: {weakest} (score: {score}).\nFocus on improving this area this week."
    return result


def lambda_handler(event, context):
    """Step Functions entry point. Receives aggregated data, returns insights."""
    if not event.get("send_email", True):
        return event

    event["insights"] = {
        "sleep_insight": generate_sleep_insight(event),
        "weekly_focus": generate_weekly_focus(event),
    }
    return event
