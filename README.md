# HealthForge

A serverless health analytics pipeline that turns Apple Health data into a personalized weekly email report. It computes sleep, fitness, recovery, consistency, and cardio scores, detects anomalies, finds patterns in your habits, and uses Google Gemini Flash to generate human-readable insights -- all delivered to your inbox every Sunday morning.

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
                    Aggregation --> Gemini Insights --> Email (SES)
```

There are two independent pipelines:

**Data Ingestion (continuous):** The Health Auto Export iOS app sends Apple Health data to an API Gateway webhook once a day. A Lambda validates the payload, queues it in SQS, and a processor Lambda parses, deduplicates, and writes metrics to DynamoDB.

**Weekly Analysis (Sunday mornings):** EventBridge triggers a Step Functions state machine that runs three Lambdas in sequence -- aggregation (scores, baselines, anomalies, correlations), insight generation (Gemini Flash), and email rendering (SES).

## Architecture

```
Stacks:
  DataStack       --> DynamoDB table (single-table design) + SQS queue + DLQ
  IngestStack     --> API Gateway (API key auth) + WebhookReceiver + DataProcessor
  AnalysisStack   --> Aggregation + Insight + EmailRenderer + Step Functions + EventBridge
```

**Key design decisions:**
- Single-table DynamoDB with composite keys (`USER#id / METRIC#name#date`) and a GSI for metric-type queries
- SQS buffering so the webhook returns 200 immediately; processing is async
- Deduplication via `attribute_not_exists(PK)` on every write -- safe to re-sync
- Gemini Flash only generates text from pre-computed results (all scoring is deterministic Python)
- No dashboard -- email-first, one report per week

## Scoring System

All scores are 0-100. The overall grade maps to A+ (95+) through D (below 55).

| Score | Components |
|-------|-----------|
| Sleep (nightly) | Duration vs baseline, efficiency, deep sleep, REM, bedtime consistency, restfulness |
| Fitness (weekly) | Activity days, calories vs average, step consistency, workout intensity, progressive load |
| Recovery (daily) | Last night's sleep, resting HR vs baseline, HRV vs baseline, respiratory rate, sleep debt |
| Consistency (weekly) | Bedtime spread, sleep duration range, step variability, workout regularity |
| Cardio (weekly) | Resting HR trend, HRV trend, walking HR, respiratory rate |

The report also includes:
- **Baselines** -- 30-day rolling averages (excluding the current week)
- **Anomalies** -- metrics exceeding 2 standard deviations for 2+ consecutive days
- **Patterns** -- workout-sleep correlation, bedtime-sleep correlation, day-of-week fingerprint
- **Personal records** -- broken or nearly broken (within 5%) all-time bests

## Example Email

```
Subject: HealthForge B+ -- Sleep 78 | Fitness 81 | Recovery 72

Hey! Here's your week in review.
Mar 2 – 8, 2026

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*YOUR SCORES*

Sleep: 78/100 (up 4)
░░░░░░░░░░░░░░░░░░░░
Fitness: 81/100 (steady)
░░░░░░░░░░░░░░░░░░░░
Recovery: 72/100 (down 3)
░░░░░░░░░░░░░░░░░░░░
Consistency: 69/100
░░░░░░░░░░░░░░░░░░░░
Cardio: 75/100
░░░░░░░░░░░░░░░░░░░░

Overall: B+ (75/100)

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*SLEEP*

Sun (03/02) -- 82
Mon (03/03) -- 71
Tue (03/04) -- 85
Wed (03/05) -- 63
Thu (03/06) -- 79
Fri (03/07) -- 74
Sat (03/08) -- 91
Average: 78

Avg sleep: 7h 12m
Avg deep: 1h 05m
Avg REM: 1h 38m
Efficiency: 91%

Best night: Sat (03/08) (91)
Worst night: Wed (03/05) (63)

Solid week overall. Wednesday dipped -- late bedtime and shorter
deep sleep. Saturday was your best night with strong REM cycles.

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*FITNESS*

Steps
  Sun (03/02) -- 8.2k
  Mon (03/03) -- 12k
  Tue (03/04) -- 6.5k
  Wed (03/05) -- 9.1k
  Thu (03/06) -- 11k
  Fri (03/07) -- 7.8k
  Sat (03/08) -- 14k
  Average: 9,800 steps/day

Workouts -- 4/7 days, 1,820 kcal total

Mon (03/03) -- Running (32m, 340 cal, HR 155)
Tue (03/04) -- Strength Training (45m, 280 cal, HR 128)
Wed (03/05) -- Rest
Thu (03/06) -- HIIT (28m, 310 cal) + Walking (40m, 180 cal)
Fri (03/07) -- Rest
Sat (03/08) -- Running (48m, 480 cal, HR 152)
Sun (03/02) -- Rest

Best day: Sat (03/08) -- 480 cal

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*RECOVERY*

Sun (03/02) -- 74
Mon (03/03) -- 68
Tue (03/04) -- 81
Wed (03/05) -- 59
Thu (03/06) -- 72
Fri (03/07) -- 70
Sat (03/08) -- 79
Average: 72

Resting HR: 56 bpm (30d avg: 58)
HRV: 42 ms (30d avg: 39)
Resp rate: 14.2 breaths/min
Walking HR: 98 bpm

Verdict: STEADY

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*CONSISTENCY*

Bedtime spread: +/-38 min
Step variability: CV 28%
Workout days: 4/7
Sleep range: 1h 22m

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*CARDIO*

Resting HR: 56 bpm (down, improving)
Walking HR: 98 bpm
HRV trend: up, good
Resp rate: 14.2 breaths/min

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*PATTERNS*

Workout days -- +18m deep sleep
Early bedtime -- +12 sleep score
Best sleep day: Saturday (avg 87)
Worst sleep day: Wednesday (avg 64)

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*ANOMALIES*

All clear -- metrics in normal range.

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*THIS WEEK'S FOCUS*

Your Wednesday sleep is consistently your weakest night (avg 64).
Try moving your bedtime 30 minutes earlier on Tue/Wed nights.
Your workout days show 18 more minutes of deep sleep -- keep the
Mon/Thu/Sat routine going.

-- -- -- -- -- -- -- -- -- -- -- -- -- --

*PERSONAL BESTS*

Best Sleep Score: 91
Highest Steps: 14,230

--
Stay consistent. Small wins compound.
-- HealthForge
```

## Project Structure

```
HealthForge/
  app.py                              # CDK entry point
  stacks/
    data_stack.py                     # DynamoDB + SQS
    ingest_stack.py                   # API Gateway + webhook + processor
    analysis_stack.py                 # Step Functions + Lambdas + EventBridge
  lambdas/
    webhook_receiver/handler.py       # Validates incoming JSON, sends to SQS
    data_processor/handler.py         # Parses metrics, deduplicates, writes to DynamoDB
    aggregation/handler.py            # Computes all scores, baselines, anomalies, correlations
    insight/handler.py                # Calls Gemini Flash for natural language insights
    email_renderer/
      handler.py                      # Renders email and sends via SES
      templates.py                    # All email formatting and section rendering
    shared/
      dates.py                        # Week range calculation, time parsing
      db.py                           # DynamoDB query helpers
      scores.py                       # Sleep, fitness, recovery, consistency, cardio scoring
      correlations.py                 # Anomaly detection, pattern analysis
      records.py                      # Personal records tracking
    shared_layer/python/              # Lambda layer (copy of shared/ + templates.py)
  scripts/
    bulk_import.py                    # Direct DynamoDB backfill from JSON export
  tests/
    unit/                             # 34 unit tests
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

### 4. Deploy

```bash
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
