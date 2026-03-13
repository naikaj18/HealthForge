# HealthForge

A serverless health analytics pipeline that turns Apple Health data into a personalized weekly email report. It computes sleep, fitness, recovery, consistency, and cardio scores, detects anomalies, finds patterns in your habits, and uses Google Gemini Flash to generate human-readable insights -- all delivered to your inbox every Sunday morning as a rich HTML dashboard.

Built entirely on AWS free tier + Gemini free tier. Costs effectively $0/month for personal use.

## How It Works

```
iPhone (Health Auto Export app)
  --> API Gateway --> Lambda --> SQS --> DynamoDB
                                          |
                              Every Sunday 9 AM ET
                                          |
                              Step Functions Pipeline
                                          |
                    Aggregation --> Gemini Insights --> HTML Email (SES)
```

There are two independent pipelines:

**Data Ingestion (continuous):** The Health Auto Export iOS app sends Apple Health data to an API Gateway webhook once a day. A Lambda validates the payload, queues it in SQS, and a processor Lambda parses, deduplicates, and writes metrics to DynamoDB.

**Weekly Analysis (Sunday mornings):** EventBridge triggers a Step Functions state machine that runs three Lambdas in sequence -- aggregation (scores, baselines, anomalies, correlations), insight generation (Gemini Flash), and email rendering (SES). The pipeline includes a Choice state that skips email if no data exists for the week.

## Architecture

```
Stacks:
  DataStack       --> DynamoDB table (single-table design) + SQS queue + DLQ + CloudWatch alarm
  IngestStack     --> API Gateway (API key auth) + WebhookReceiver + DataProcessor
  AnalysisStack   --> Aggregation + Insight + EmailRenderer + Step Functions + EventBridge + CloudWatch alarm
```

**Key design decisions:**
- Single-table DynamoDB with composite keys (`USER#id / METRIC#name#date`) and a GSI for metric-type queries
- SQS buffering so the webhook returns 200 immediately; processing is async
- Deduplication via `attribute_not_exists(PK)` on every write -- safe to re-sync
- DynamoDB query pagination handled for large date ranges (30-day baselines, 90-day correlations)
- Gemini Flash only generates text from pre-computed results (all scoring is deterministic Python)
- HTML email with inline CSS for Gmail/Outlook compatibility, plus plain text fallback
- Lambda Layer for shared code (auto-synced via `scripts/build_layer.sh`)
- CloudWatch alarms on the DLQ and Step Functions failures

## Scoring System

All scores are 0-100, computed as weighted averages of sub-components. If a component's data is missing (e.g., no deep sleep data), its weight is redistributed to the remaining components. All comparisons are **relative to your own 30-day baselines**, not universal standards.

The overall grade is a simple average of all 5 scores, mapped to A+ (95+) through D (below 55).

### Sleep Score (per night)

| Component | Weight | Logic |
|-----------|--------|-------|
| Duration | 25% | 100 if within ±30min of your 30-day average total sleep. Degrades linearly beyond. |
| Efficiency | 25% | `sleep_time / (sleep_time + awake_time) × 100`, used directly as the score. |
| Deep sleep | 20% | 100 if at or above your 30-day deep sleep average. Scales linearly below. |
| REM sleep | 15% | 100 if at or above your 30-day REM average. Scales linearly below. |
| Bedtime consistency | 10% | Distance from your average bedtime. 100 if same time, loses 20 pts per 15 minutes off. Handles midnight wrap. |
| Restfulness | 5% | 100 if < 15min awake. Loses 2 points per extra minute. |

The weekly Sleep score shown in the report is the **average of all nightly scores**.

### Fitness Score (weekly)

| Component | Weight | Logic |
|-----------|--------|-------|
| Active days | 30% | `(days with ≥30min exercise / 7) × 100`. |
| Calories vs average | 25% | `(this week / 30-day weekly average) × 100`, capped at 120. |
| Step consistency | 20% | Coefficient of variation (CV) of daily steps. CV ≤ 10% = 100, CV ≥ 50% = 0. Rewards even daily activity. |
| Workout intensity | 15% | `(avg workout HR / estimated max HR) × 100`. Max HR estimated at 190. Skipped if no workouts. |
| Progressive load | 10% | `(this week calories / last week calories) × 100`, capped at 120. Rewards increasing effort. |

### Recovery Score (daily)

| Component | Weight | Logic |
|-----------|--------|-------|
| Last night's sleep score | 35% | Directly uses the nightly sleep score. |
| Resting HR vs baseline | 25% | 100 if at or below 30-day average RHR. Higher = poor recovery. |
| HRV vs baseline | 20% | 100 if at or above 30-day average HRV. Higher = better recovery. |
| Respiratory rate vs baseline | 15% | 100 if at or below 30-day average. Elevated = stress/illness signal. |
| Sleep debt | 5% | 100 if 7-day average sleep ≥ 7 hours. Scales linearly below. |

The weekly Recovery score is the **average of all daily scores**. The verdict is: PUSH IT (80+), STEADY (60-79), or RECOVER (below 60).

### Consistency Score (weekly)

| Component | Weight | Logic |
|-----------|--------|-------|
| Bedtime spread | 35% | Std dev of bedtimes. ≤ 15min = 100, ≥ 90min = 0. Normalized around midnight. |
| Sleep duration range | 25% | Max minus min sleep hours. ≤ 1h = 100, ≥ 5h = 0. |
| Step variability | 20% | CV of daily steps. ≤ 10% = 100, ≥ 50% = 0. |
| Workout regularity | 20% | 3+ workouts = 100, 2 = 66, 1 = 33, 0 = 0. |

### Cardio Score (weekly)

| Component | Weight | Logic |
|-----------|--------|-------|
| Resting HR vs baseline | 30% | 100 if at or below 30-day average. Lower = fitter. |
| HRV vs baseline | 30% | 100 if at or above 30-day average. Higher = fitter. |
| Walking HR vs baseline | 20% | 100 if at or below average. Lower = more efficient. |
| RHR trend | 10% | 100 if dropping over the week, 50 if flat, 0 if rising. |
| HRV trend | 10% | 100 if rising over the week, 50 if flat, 0 if dropping. |

### Overall Grade

| Score | Grade |
|-------|-------|
| 95+ | A+ |
| 90-94 | A |
| 85-89 | A- |
| 80-84 | B+ |
| 75-79 | B |
| 70-74 | B- |
| 65-69 | C+ |
| 60-64 | C |
| 55-59 | C- |
| Below 55 | D |

### Additional Analysis

The report also includes:
- **Baselines** -- 30-day rolling averages computed from data before the current week
- **Anomalies** -- metrics exceeding 2 standard deviations for 2+ consecutive days (requires 14+ days of history)
- **Patterns** -- workout-sleep correlation, bedtime-sleep correlation, day-of-week fingerprint (requires 28+ days of history)
- **This week's bests** -- best sleep score, highest steps, fitness score, lowest RHR, highest HRV for the week

## Email Format

The email is an HTML dashboard with:
- Dark hero header with overall grade in a colored circle
- Color-coded score bars (green 80+, amber 60-79, red below 60)
- Step and workout bars with daily breakdowns
- Card-based sections for Sleep, Fitness, Recovery, Consistency, Cardio, Patterns, Anomalies
- Gemini-generated sleep insights and weekly focus recommendations
- Plain text fallback for non-HTML email clients

Subject format: `HealthForge B — Sleep 85 | Fitness 58 | Recovery 92 (Mar 5 – 11, 2026)`

## Project Structure

```
HealthForge/
  app.py                              # CDK entry point
  cdk.json                            # CDK configuration
  requirements.txt                    # Production dependencies
  requirements-dev.txt                # Dev/test dependencies
  ARCHITECTURE.md                     # Detailed architecture documentation
  PRODUCT_BRIEF.md                    # Product specification
  stacks/
    data_stack.py                     # DynamoDB + SQS + DLQ + CloudWatch alarm
    ingest_stack.py                   # API Gateway + webhook + processor
    analysis_stack.py                 # Step Functions + Lambdas + EventBridge + CloudWatch alarm
  lambdas/
    webhook_receiver/handler.py       # Validates incoming JSON, sends to SQS
    data_processor/handler.py         # Parses metrics, deduplicates, writes to DynamoDB
    aggregation/handler.py            # Computes all scores, baselines, anomalies, correlations
    insight/handler.py                # Calls Gemini Flash for natural language insights
    email_renderer/
      handler.py                      # Renders HTML email and sends via SES
      templates.py                    # HTML email formatting and section rendering
    shared/
      dates.py                        # Week range calculation, time parsing
      db.py                           # DynamoDB query helpers (with pagination)
      scores.py                       # Sleep, fitness, recovery, consistency, cardio scoring
      correlations.py                 # Anomaly detection, pattern analysis
      records.py                      # Weekly bests tracking
    shared_layer/python/              # Lambda layer (auto-synced via scripts/build_layer.sh)
  scripts/
    build_layer.sh                    # Copies shared/ + templates.py into Lambda layer
    bulk_import.py                    # Direct DynamoDB backfill from JSON export
    test_email_local.py               # Local email rendering test script
  tests/unit/
    test_scores.py                    # Scoring algorithm tests
    test_correlations.py              # Anomaly detection + pattern tests
    test_dates.py                     # Date utility tests
    test_db.py                        # DynamoDB helper tests
    test_records.py                   # Weekly bests tests
    test_templates.py                 # HTML template rendering tests
    test_email_renderer.py            # Full email render + subject line tests
    test_webhook_receiver.py          # Webhook validation tests
    test_data_processor.py            # Data processor tests
    test_insight.py                   # Gemini insight handler tests
```

## Setup

### Prerequisites

- Python 3.12+
- AWS CLI configured with credentials
- AWS CDK v2 (`npm install -g aws-cdk`)
- Google Gemini API key (free tier at https://aistudio.google.com)
- Health Auto Export iOS app (~$5 one-time)
- An email address verified in AWS SES

### 1. Clone and install

```bash
git clone https://github.com/naikaj18/HealthForge.git
cd HealthForge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set SSM parameters

```bash
aws ssm put-parameter --name /healthforge/gemini-api-key --value "YOUR_KEY" --type SecureString
aws ssm put-parameter --name /healthforge/sender-email --value "you@example.com" --type String
aws ssm put-parameter --name /healthforge/recipient-email --value "you@example.com" --type String
```

### 3. Verify sender email in SES

```bash
aws ses verify-email-identity --email-address you@example.com
```

Check your inbox and click the verification link.

### 4. Build the Lambda layer and deploy

```bash
bash scripts/build_layer.sh
cdk deploy --all
```

This creates three stacks: HealthForgeData, HealthForgeIngest, and HealthForgeAnalysis.

### 5. Configure Health Auto Export

1. Open the app on your iPhone
2. Create a new REST API automation
3. Set the URL to: `https://{api-id}.execute-api.{region}.amazonaws.com/prod/ingest`
4. Add header -- Key: `x-api-key`, Value: (from API Gateway console or CDK output)
5. Data Type: Health Metrics, All Selected
6. Export Format: JSON, Version: v2
7. Sync Cadence: 1 day
8. Tap Update

### 6. Backfill historical data (optional)

Export your full health data from the app as JSON, then:

```bash
python scripts/bulk_import.py /path/to/export.json
```

### 7. Test

Trigger the pipeline manually:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:{region}:{account}:stateMachine:HealthForge-WeeklyReport \
  --input '{"user_id": "default"}'
```

Or wait for Sunday 9 AM ET.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Cost

For a single user with daily syncs and weekly reports:

| Service | Free Tier | Your Usage | Cost |
|---------|-----------|------------|------|
| DynamoDB | 25 GB storage, 25 WCU/RCU | ~100 MB/year | $0 |
| Lambda | 1M requests/month | ~200/month | $0 |
| API Gateway | 1M requests/month | ~30/month | $0 |
| SQS | 1M requests/month | ~30/month | $0 |
| Step Functions | 4,000 transitions/month | ~12/month | $0 |
| SES | 3,000 emails/month (free with EC2) | 4/month | ~$0.00 |
| Gemini Flash | Free tier | 8 calls/month | $0 |

Total: effectively **$0/month**.

## Useful Commands

```bash
cdk ls          # List all stacks
cdk synth       # Synthesize CloudFormation templates
cdk deploy      # Deploy to AWS
cdk diff        # Compare deployed vs local
cdk destroy     # Tear down all stacks
```
