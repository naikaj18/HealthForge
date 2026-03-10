# HealthForge — Architecture Document

## Overview

HealthForge turns Apple Health data into actionable health insights delivered via email. Data flows from your iPhone to AWS, gets processed and stored, then analyzed on a schedule to generate personalized health briefings.

**Core principle:** All computation (scores, averages, anomaly detection) is done in code. The LLM (Gemini Flash) only writes human-friendly interpretations of pre-computed results.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              HealthForge                                    │
│                                                                             │
│  ┌───────────┐         ┌──────────────────────────────────────────────────┐ │
│  │           │         │              AWS Cloud                           │ │
│  │  iPhone   │  JSON   │                                                  │ │
│  │  Health   │────────▶│  API Gateway → Lambda → SQS → Lambda → DynamoDB │ │
│  │  Auto     │ every   │                                                  │ │
│  │  Export   │ 2 hrs   │  EventBridge → Step Functions → Gemini → SES     │ │
│  │           │         │                                    │              │ │
│  └───────────┘         │                                    ▼              │ │
│                        │                              Your Inbox           │ │
│                        └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Two Pipelines

The system has two independent pipelines that share the same database:

| Pipeline | Trigger | Purpose |
|----------|---------|---------|
| **Ingestion Pipeline** | Phone sends data every 2 hours | Receive → validate → store health data |
| **Analysis Pipeline** | Scheduled (Sunday 10 AM) | Read stored data → compute scores → generate insights → email |

They never run at the same time in a dependent way. Ingestion writes data, analysis reads it.

The weekly schedule (Sunday morning covering Sun–Sat) ensures all sleep data is complete — no risk of partial data from the current night.

---

## Pipeline 1: Data Ingestion (Real-Time)

### Flow Diagram

```
┌──────────────┐     HTTPS POST      ┌───────────────┐
│    iPhone     │────────────────────▶│  API Gateway   │
│ Health Auto   │  JSON payload       │  /ingest       │
│ Export App    │                     │  /upload       │
└──────────────┘                     └───────┬───────┘
                                             │
                                    Forwards request to
                                             │
                                             ▼
                                    ┌────────────────┐
                                    │   Webhook       │
                                    │   Receiver      │
                                    │   Lambda        │
                                    │                 │
                                    │ • Parse JSON    │
                                    │ • Validate      │
                                    │   structure     │
                                    │ • Return 200    │
                                    │   immediately   │
                                    └────────┬───────┘
                                             │
                                    Sends message to
                                             │
                                             ▼
                              ┌──────────────────────────┐
                              │         SQS Queue         │
                              │    (message buffer)       │
                              │                           │
                              │  If processing fails 3x:  │
                              │  ┌──────────────────────┐ │
                              │  │   Dead Letter Queue  │ │
                              │  │  (keeps failed msgs  │ │
                              │  │   for 14 days)       │ │
                              │  └──────────────────────┘ │
                              └────────────┬─────────────┘
                                           │
                              Triggers automatically
                              (batch of up to 10 msgs)
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │     Data Processor        │
                              │     Lambda                │
                              │                           │
                              │  For each metric:         │
                              │  1. Is it supported?      │
                              │     (sleep, steps, HR...) │
                              │  2. Parse the date        │
                              │  3. Already in DB?        │
                              │     → Skip (deduplicate)  │
                              │  4. Write to DynamoDB     │
                              └────────────┬─────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │       DynamoDB            │
                              │                           │
                              │  One row per metric       │
                              │  per user per day         │
                              └──────────────────────────┘
```

### Why SQS in the Middle?

Without SQS (bad):
```
Phone → API Gateway → Lambda (process + write to DB) → Response
         If this takes 30 seconds or crashes, your phone gets an error.
         Data could be lost.
```

With SQS (good):
```
Phone → API Gateway → Lambda (just queue it) → 200 OK (instant, <1 sec)
                              ↓
                        SQS holds the message safely
                              ↓
                        Processor Lambda handles it at its own pace
                        If it crashes → SQS retries automatically (up to 3x)
                        If it still fails → DLQ preserves the message
```

**Result:** Your phone always gets a fast response. No data is ever lost.

### What the Phone Sends

Health Auto Export sends JSON like this every 2 hours:

```json
{
  "data": {
    "metrics": [
      {
        "name": "sleep_analysis",
        "units": "min",
        "data": [
          {
            "date": "2026-03-08 23:15:00",
            "asleep": 385,
            "inBed": 440,
            "deep": 62,
            "rem": 88,
            "core": 235,
            "source": "Apple Watch"
          }
        ]
      },
      {
        "name": "step_count",
        "units": "count",
        "data": [
          { "date": "2026-03-08", "qty": 8423 }
        ]
      },
      {
        "name": "resting_heart_rate",
        "units": "bpm",
        "data": [
          { "date": "2026-03-08", "qty": 58 }
        ]
      },
      {
        "name": "active_energy_burned",
        "units": "kcal",
        "data": [
          { "date": "2026-03-08", "qty": 520 }
        ]
      },
      {
        "name": "heart_rate_variability",
        "units": "ms",
        "data": [
          { "date": "2026-03-08", "qty": 42 }
        ]
      },
      {
        "name": "workout",
        "units": "min",
        "data": [
          {
            "date": "2026-03-08 17:30:00",
            "name": "Running",
            "duration": 35,
            "totalEnergyBurned": 380
          }
        ]
      }
    ]
  }
}
```

### Metrics We Ingest

| Category | Metric | What It Contains |
|----------|--------|-----------------|
| **Sleep** | `sleep_analysis` | Total sleep, deep/REM/core stages, in-bed time, WASO |
| **Fitness** | `step_count` | Daily step total |
| **Fitness** | `active_energy_burned` | Active calories burned |
| **Fitness** | `apple_exercise_time` | Minutes of exercise |
| **Fitness** | `workout` | Workout type, duration, calories |
| **Fitness** | `vo2_max` | VO2 Max estimate |
| **Heart** | `resting_heart_rate` | Resting HR in bpm |
| **Heart** | `heart_rate_variability` | HRV (SDNN) in ms |
| **Heart** | `walking_heart_rate_average` | Walking HR in bpm |

### Deduplication

Health Auto Export sends overlapping data. Example:
- At 2:00 PM it sends today's steps so far (5,000)
- At 4:00 PM it sends today's steps again (7,200)
- At 6:00 PM it sends again (8,423)

Our processor uses `ConditionExpression="attribute_not_exists(PK)"` — it only writes the **first** value it sees for a given metric+date. This keeps things simple for now. In the future, we can switch to "last write wins" if we want the most up-to-date value within a day.

---

## Pipeline 2: Analysis & Email (Scheduled — Built in Weeks 2-4)

### Flow Diagram

```
┌──────────────────┐
│   EventBridge     │
│   (cron scheduler)│
│                   │
│  Sunday 10:00 AM ────┤
└──────────────────┘   │
                        │
                        ▼
          ┌──────────────────────────────────────────┐
          │           Step Functions                  │
          │        (orchestrates 3 steps)             │
          │                                          │
          │  ┌────────────────────────────────────┐  │
          │  │  Step 1: AGGREGATION LAMBDA         │  │
          │  │                                     │  │
          │  │  Reads from DynamoDB:               │  │
          │  │  • Last night's sleep data          │  │
          │  │  • Last 7/30/90 days of metrics     │  │
          │  │                                     │  │
          │  │  Computes:                          │  │
          │  │  • Rolling averages (7d, 30d, 90d)  │  │
          │  │  • Personal baselines               │  │
          │  │  • Standard deviations              │  │
          │  │  • Sleep Score (0-100)               │  │
          │  │  • Fitness Score (0-100)             │  │
          │  │  • Recovery Score (0-100)            │  │
          │  │  • Anomaly detection (2 std devs)   │  │
          │  │  • Day-of-week fingerprint           │  │
          │  │  • Correlations                     │  │
          │  │                                     │  │
          │  │  Output: JSON with all numbers      │  │
          │  └──────────────┬──────────────────────┘  │
          │                 │                          │
          │                 ▼                          │
          │  ┌────────────────────────────────────┐   │
          │  │  Step 2: INSIGHT LAMBDA             │   │
          │  │                                     │   │
          │  │  Sends COMPUTED numbers to           │   │
          │  │  Gemini Flash API:                   │   │
          │  │                                     │   │
          │  │  "Sleep score: 78. Deep sleep 62min  │   │
          │  │   (15% above baseline). Bedtime was  │   │
          │  │   23min later. On days with pre-6PM  │   │
          │  │   workouts, deep sleep averages 22min │   │
          │  │   more (47 of 52 instances)."        │   │
          │  │                                     │   │
          │  │  Gemini returns:                    │   │
          │  │  "Solid deep sleep despite a later   │   │
          │  │   bedtime. Afternoon workouts keep   │   │
          │  │   paying off — try to train before   │   │
          │  │   6 PM today."                      │   │
          │  │                                     │   │
          │  │  NOTE: Only computed summaries are   │   │
          │  │  sent to Gemini, never raw health    │   │
          │  │  data.                              │   │
          │  └──────────────┬──────────────────────┘  │
          │                 │                          │
          │                 ▼                          │
          │  ┌────────────────────────────────────┐   │
          │  │  Step 3: EMAIL LAMBDA               │   │
          │  │                                     │   │
          │  │  Combines:                          │   │
          │  │  • Template (scores, numbers)       │   │
          │  │  • Gemini insight paragraph         │   │
          │  │                                     │   │
          │  │  Sends via SES to your inbox        │   │
          │  └────────────────────────────────────┘   │
          └──────────────────────────────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Your Inbox   │
                    │               │
                    │  Morning      │
                    │  Briefing     │
                    │  or Weekly    │
                    │  Deep-Dive    │
                    └──────────────┘
```

### Why Step Functions?

We could chain these Lambda calls in code. But Step Functions gives us:

```
Without Step Functions:
  Lambda A calls Lambda B calls Lambda C
  If B fails → A doesn't know, C never runs, debugging is a nightmare

With Step Functions:
  Step Functions calls A → then B → then C
  If B fails → automatic retry with backoff
  Every step is logged and visible in AWS console
  You can see exactly where it failed and why
```

### Email: Weekly Report (Sunday 10 AM, covers Sunday–Saturday)

```
Subject: HealthForge — Week of Mar 2-8 | Sleep 74 ↑ Fitness 81 Recovery 77

WEEK AT A GLANCE
  Sleep:    74 (↑3 from last week)
  Fitness:  81 (steady)
  Recovery: 77 (↓2)

SLEEP
  Mon: 82  Tue: 89  Wed: 71  Thu: 58  Fri: 75  Sat: 80
  Best night: Tuesday (89) — 7h12m, early bedtime
  Worst night: Thursday (58) — 5h30m, late screen time
  Average: 6h38m | Efficiency: 88% | Bedtime consistency: ±22 min

FITNESS
  Active days: 5/7 | Calories: 3,240 (↑8%)
  Workout streak: 12 days
  Top session: Thursday run — 45 min, 420 cal

RECOVERY
  Mon: 81  Tue: 84  Wed: 72  Thu: 65  Fri: 78  Sat: 82
  Average: 77 | Trend: stable

THIS WEEK'S INSIGHT
  [Gemini-generated paragraph from computed correlations]

ONE THING TO TRY
  Your Thursday sleep is consistently your worst (avg 64).
  Consider a wind-down routine on Wednesday nights.

HEART RATE
  RHR: 57 bpm (normal) | HRV: 44ms (stable)

⚠️ ANOMALY (if any)
  RHR was elevated Thu-Fri (67 bpm vs 58 bpm baseline, 2.1 std devs).
  Last time this happened: Feb 12 (resolved after 3 days).
```

---

## Database Design (DynamoDB)

### Single-Table Design

Everything lives in one table. The PK and SK determine what type of record it is:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DynamoDB: HealthForge                            │
│                                                                         │
│  ┌──────────────┬────────────────────────────────┬────────────────────┐ │
│  │     PK       │            SK                  │      data          │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ METRIC#sleep_analysis#2026-03-08│ {asleep:385,      │ │
│  │              │                                │  deep:62, rem:88}  │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ METRIC#step_count#2026-03-08   │ {qty: 8423}        │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ METRIC#resting_heart_rate      │ {qty: 58}          │ │
│  │              │ #2026-03-08                    │                    │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ METRIC#workout#2026-03-08      │ {name:"Running",   │ │
│  │              │                                │  duration:35,      │ │
│  │              │                                │  calories:380}     │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ BASELINE#sleep_analysis#30d    │ {avg_asleep: 402,  │ │
│  │              │                                │  std: 35}          │ │
│  ├──────────────┼────────────────────────────────┼────────────────────┤ │
│  │ USER#naikaj  │ BASELINE#resting_heart_rate#30d│ {avg: 58, std: 4}  │ │
│  └──────────────┴────────────────────────────────┴────────────────────┘ │
│                                                                         │
│  GSI1 (for querying by metric type + date range):                       │
│  ┌──────────────────────────────────┬────────────┐                      │
│  │          GSI1PK                  │  GSI1SK    │                      │
│  ├──────────────────────────────────┼────────────┤                      │
│  │ USER#naikaj#METRIC#sleep_analysis│ 2026-03-08 │                      │
│  │ USER#naikaj#METRIC#sleep_analysis│ 2026-03-07 │                      │
│  │ USER#naikaj#METRIC#sleep_analysis│ 2026-03-06 │                      │
│  │ USER#naikaj#METRIC#step_count   │ 2026-03-08 │                      │
│  └──────────────────────────────────┴────────────┘                      │
│                                                                         │
│  Query example:                                                         │
│  "Give me all sleep data from last 30 days"                             │
│  → GSI1PK = "USER#naikaj#METRIC#sleep_analysis"                        │
│    GSI1SK BETWEEN "2026-02-06" AND "2026-03-08"                         │
│  → Returns 30 rows, sorted by date. Fast, cheap, no table scan.        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Single-Table?

In SQL you'd have separate tables: `users`, `sleep_records`, `step_records`, `baselines`, etc.

In DynamoDB, you put everything in one table and use the key structure to differentiate record types. Benefits:
- One table to manage, monitor, and back up
- All data for a user is co-located (fast queries)
- Free tier covers one table easily (25 GB, 25 read/write capacity units)
- Multi-tenant ready — just change the user ID in PK

### Common Query Patterns

| Query | How |
|-------|-----|
| All data for a user | PK = `USER#naikaj` |
| Last night's sleep | PK = `USER#naikaj`, SK = `METRIC#sleep_analysis#2026-03-08` |
| Last 30 days of sleep | GSI1: GSI1PK = `USER#naikaj#METRIC#sleep_analysis`, GSI1SK between dates |
| User's baselines | PK = `USER#naikaj`, SK begins_with `BASELINE#` |
| Specific baseline | PK = `USER#naikaj`, SK = `BASELINE#sleep_analysis#30d` |

---

## CDK Stack Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CDK App (app.py)                       │
│                                                          │
│  ┌─────────────────────┐   ┌──────────────────────────┐ │
│  │   HealthForgeData    │   │   HealthForgeIngest       │ │
│  │   (data_stack.py)    │   │   (ingest_stack.py)       │ │
│  │                      │   │                           │ │
│  │  • DynamoDB Table    │──▶│  • API Gateway            │ │
│  │    (HealthForge)     │   │    - POST /ingest         │ │
│  │                      │   │    - POST /upload         │ │
│  │  • SQS Queue         │──▶│  • Webhook Receiver λ     │ │
│  │    (HealthForge-     │   │  • Data Processor λ       │ │
│  │     Ingest)          │   │                           │ │
│  │                      │   │  Permissions:             │ │
│  │  • Dead Letter Queue │   │  • λ → SQS send          │ │
│  │    (HealthForge-     │   │  • λ → DynamoDB r/w      │ │
│  │     Ingest-DLQ)      │   │  • SQS → triggers λ      │ │
│  └─────────────────────┘   └──────────────────────────┘ │
│                                                          │
│  Future stacks:                                          │
│  ┌─────────────────────┐   ┌──────────────────────────┐ │
│  │  HealthForgeAnalysis │   │  HealthForgeAuth          │ │
│  │  (Week 2-4)          │   │  (Phase 2)                │ │
│  │                      │   │                           │ │
│  │  • EventBridge rules │   │  • Cognito User Pool      │ │
│  │  • Step Functions    │   │  • Per-user API keys      │ │
│  │  • Aggregation λ     │   │  • Auth middleware        │ │
│  │  • Insight λ (Gemini)│   │                           │ │
│  │  • Email λ (SES)     │   │                           │ │
│  └─────────────────────┘   └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Why Separate Stacks?

- **DataStack** contains the database. If you delete or redeploy the IngestStack, the database survives (`RemovalPolicy.RETAIN`).
- **IngestStack** contains the API and Lambdas. These change frequently. Safe to redeploy without risking data.
- **AnalysisStack** (future) will contain scheduled jobs. Independent deployments.
- **AuthStack** (future) will add Cognito. Can be added without touching existing stacks.

---

## AWS Services Used

| Service | What It Does | Why We Chose It | Free Tier |
|---------|-------------|-----------------|-----------|
| **API Gateway** | HTTPS endpoint for phone to send data | Managed, auto-scaling, no servers | 1M calls/month |
| **Lambda** | Runs our Python code on demand | No servers, pay per execution, scales to zero | 1M requests/month |
| **SQS** | Message queue between receiver and processor | Decouples ingestion, auto-retry, prevents data loss | 1M requests/month |
| **DynamoDB** | NoSQL database for all health data | Fast, serverless, single-table design, free tier generous | 25 GB, 25 RCU/WCU |
| **Step Functions** | Orchestrates analysis pipeline | Visual workflow, retry logic, error handling | 4,000 transitions/month |
| **EventBridge** | Cron scheduler for daily/weekly emails | Serverless cron, no EC2 needed | Free for rules |
| **SES** | Sends emails | Cheapest email service on AWS | $0.10/1,000 emails |
| **Gemini Flash** | Generates human-friendly insight text | Free tier, good quality, fast | 15 req/min free |
| **SSM Parameter Store** | Stores Gemini API key securely | Free, encrypted, easy Lambda access | Free |
| **CloudWatch** | Logs and monitoring | Auto-captures Lambda logs | 5 GB free |

---

## Security & Privacy

```
┌──────────────────────────────────────────────────────┐
│                  Data Flow & Privacy                  │
│                                                       │
│  iPhone ──── HTTPS ────▶ AWS (all processing)        │
│                           │                           │
│                           ├── Raw health data stays   │
│                           │   in DynamoDB (encrypted   │
│                           │   at rest)                │
│                           │                           │
│                           ├── Only COMPUTED SUMMARIES  │
│                           │   sent to Gemini Flash    │
│                           │   (never raw health data) │
│                           │                           │
│                           └── Emails sent via SES     │
│                               (to your inbox only)    │
│                                                       │
│  What Gemini sees:                                   │
│  ✗ NOT: "Heart rate readings: 58,62,59,61,57..."     │
│  ✓ YES: "RHR avg 58bpm, 2bpm below 30-day baseline" │
└──────────────────────────────────────────────────────┘
```

- All data encrypted at rest (DynamoDB default encryption)
- All data in transit over HTTPS
- Lambda functions have least-privilege IAM permissions (only access what they need)
- Gemini receives pre-computed summaries, never raw health data
- Single-user for now; Cognito auth scoping planned for multi-user

---

## Build Order

| Week | What | Status |
|------|------|--------|
| **Week 1** | CDK stacks + API Gateway + Lambda + DynamoDB + SQS. Health Auto Export configured. Raw data landing. | ✅ Built |
| **Week 2** | Derived metrics (rolling avgs, baselines). Sleep Score + Fitness Score formulas. | Upcoming |
| **Week 3** | Weekly report email with Step Functions + Gemini Flash insight. EventBridge Sunday 10 AM. | Upcoming |
| **Week 4** | Recovery score + anomaly detection (included in weekly report). | Upcoming |
| **Week 5+** | Correlation engine, query API, web app, Cognito auth. | Future |

---

## Future: Web App & Multi-User (Phase 2)

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   Browser     │────▶│  Cognito      │────▶│  API Gateway         │
│   (React?)    │     │  Login        │     │  /query              │
└──────────────┘     └──────────────┘     └──────────┬──────────┘
                                                      │
                                                      ▼
                                          ┌──────────────────────┐
                                          │  Query Lambda         │
                                          │                       │
                                          │  User: "How did I     │
                                          │  sleep on workout     │
                                          │  days?"               │
                                          │                       │
                                          │  1. Query DynamoDB    │
                                          │     for sleep +       │
                                          │     workout data      │
                                          │  2. Compute           │
                                          │     comparison        │
                                          │  3. Send summary to   │
                                          │     Gemini Flash      │
                                          │  4. Return answer     │
                                          └──────────────────────┘
```

The data model already supports multiple users (`USER#<cognito_sub>` partition key). Adding multi-user is a matter of:
1. Adding Cognito authentication
2. Extracting user ID from the auth token instead of hardcoding "default"
3. Adding per-user API keys for Health Auto Export webhook
