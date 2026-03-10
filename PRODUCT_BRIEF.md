# HealthForge — Product Brief

## One-Line Pitch
"Turns your Apple Health data into a personal health analyst — delivered to your inbox."

## Focus
- **PRIMARY:** Sleep health (duration, efficiency, stages, debt, consistency, correlations)
- **PRIMARY:** Fitness (steps, workouts, active calories, streaks, progressive overload)
- **BACKGROUND:** Heart rate (silent monitoring, anomaly alerts only)

## Budget
- ~$5 total setup
- Health Auto Export iOS app (~$5 one-time)
- AWS free tier (~$0.01/month for SES)
- Gemini Flash free tier ($0/month)

## Tech Stack
- **Infrastructure:** AWS CDK (Python)
- **Backend:** FastAPI on Lambda
- **Database:** DynamoDB (single-table design, `USER#<id>` partition key for multi-tenant ready)
- **Orchestration:** Step Functions
- **Queue:** SQS
- **LLM:** Google Gemini Flash (free tier — insight generation & conversational queries, not computation)
- **Email:** SES
- **Auth (later):** Cognito
- **Scheduling:** EventBridge

## Data Source
- Apple Health via **Health Auto Export** iOS app
- Auto-syncs every 2 hours to API Gateway webhook endpoint
- Fallback: manual XML export upload via FastAPI endpoint

## Architecture
```
iPhone (Health Auto Export, every 2hrs)
  → API Gateway (authenticated)
    → SQS (buffer incoming data)
      → Lambda (parse & validate & deduplicate)
        → DynamoDB (structured health records)

EventBridge (daily/weekly schedules)
  → Step Functions
    → Lambda (aggregate, correlate, detect anomalies)
      → Gemini Flash (interpret computed results)
        → SES (insight email / anomaly alert)

FastAPI (on Lambda via API Gateway)
  → Query endpoint: natural language → DynamoDB queries → Gemini Flash interprets
  → Upload endpoint: manual XML export (fallback)
```

## Three Core Scores

### Sleep Score (0-100, nightly)
| Component | Weight |
|-----------|--------|
| Duration vs personal 30-day avg | 25% |
| Efficiency (asleep / in bed) | 25% |
| Deep Sleep vs baseline | 20% |
| REM vs baseline | 15% |
| Bedtime consistency | 10% |
| Restfulness (WASO) | 5% |

### Fitness Score (0-100, weekly)
| Component | Weight |
|-----------|--------|
| Activity consistency (days with 30+ active min) | 30% |
| Volume (active calories vs avg) | 25% |
| Step consistency | 20% |
| Workout intensity | 15% |
| Progressive load | 10% |

### Recovery Readiness (0-100, daily morning)
| Component | Weight |
|-----------|--------|
| Last night's sleep score | 35% |
| Resting HR vs 30-day avg | 25% |
| HRV vs 30-day avg | 20% |
| Recent 3-day training load | 15% |
| 7-day sleep debt | 5% |

Output: "Push it" (80+) / "Steady" (60-79) / "Recover" (<60)

## Email Touchpoints

### Weekly Report (Sunday 10 AM, covers Sunday–Saturday)
- Week at a glance (3 scores with arrows vs prior week)
- Sleep deep-dive (best/worst night, nightly scores, averages, consistency)
- Fitness recap (active days, calories, streak, workouts)
- Recovery trends (daily recovery scores across the week)
- This week's insight (Gemini Flash-generated from computed correlations)
- One thing to try this week
- Heart rate check (minimal unless anomaly)
- Anomaly callouts if any metric exceeded 2 std devs from 30-day baseline

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
```

## Apple Health Metrics to Ingest

### Sleep
- `sleepAnalysis` (total sleep, stages: Core/Deep/REM, inBed intervals)
- Derived: sleep onset time, wake time, efficiency, WASO

### Fitness
- `activeEnergyBurned`
- `stepCount`
- `appleExerciseTime`
- `workout` (type, duration, calories)
- `vo2Max`

### Heart Rate (Background)
- `restingHeartRate`
- `heartRateVariabilitySDNN`
- `walkingHeartRateAverage`

## Derived Metrics to Compute
- Rolling averages (7-day, 30-day, 90-day)
- Personal baselines per metric (adaptive, recalculated weekly)
- Standard deviation bands for anomaly detection
- Sleep efficiency, sleep debt (7-day rolling)
- Day-of-week fingerprint (per-metric avg by weekday, 90-day rolling)
- RHR/HRV deviation from baseline
- Training load (3-day rolling active calories)

## DynamoDB Key Design (Multi-Tenant Ready)
```
PK: USER#<cognito_sub>
SK: METRIC#<metricType>#<date>

GSI1:
  PK: USER#<userId>#METRIC#<metricType>
  SK: <date>

Baselines:
  PK: USER#<userId>
  SK: BASELINE#<metricType>#<window>
```

## 5 "Aha" Features
1. **Behavioral Correlation** — "Workouts before 6PM = 22 min more deep sleep. 47 of 52 instances."
2. **Day-of-Week Fingerprint** — "Your worst sleep is consistently Thursday (avg 64). Best is Sunday (83)."
3. **Personal Recovery Curve** — "After hard workouts, your RHR takes 2 days to return to baseline."
4. **Sleep Efficiency Drift** — "Efficiency dropped 91% → 84% over 6 weeks. Bedtime shifted 35 min later — explains 80%."
5. **"What Changed?" Detector** — "Deep sleep down 14%, steps down 22%. Biggest shift: bedtime moved 35 min later."

## Web App Features (Beyond Email)
- Conversational query API ("How did I sleep on days I worked out?")
- Experiment tracker ("Stop caffeine after 2pm for 2 weeks" → auto-compare before/during/after)
- Doctor export (90-day PDF summary)
- Week/month comparison view
- Personal records board
- Morning decision screen (one-glance recovery recommendation)

## Anti-Features
- No gamification that punishes rest days
- No real-time dashboard (email-first)
- No anxiety-inducing alerts for normal variation
- No medical/diagnostic language
- No more than 1 email per day
- Never show raw numbers without personal context
- LLM for synthesis only, templates for reporting

## Multi-User Design (Build Later)
- Cognito user pool for auth
- Per-user API key for Health Auto Export webhook
- All data scoped by `USER#<cognito_sub>` partition key
- Per-user EventBridge schedules or fan-out
- Privacy: health data stored in AWS, LLM calls send only computed summaries to Gemini (not raw data)

## Build Order
1. **Week 1:** CDK stacks + API Gateway + Lambda + DynamoDB. Health Auto Export configured. Raw data landing.
2. **Week 2:** Derived metrics (rolling avgs, baselines). Sleep Score + Fitness Score formulas.
3. **Week 3:** Weekly report email with Step Functions + Gemini Flash insight. EventBridge Sunday 10 AM schedule.
4. **Week 4:** Recovery score + anomaly detection (included in weekly report).
5. **Week 5+:** Correlation engine, query API, web app, iterate.

## Build Phases
- **Phase 1 (Now):** Email-only product, single user, no auth, templates + Gemini Flash for insights
- **Phase 2 (Later):** Web app with conversational queries, Cognito auth, multi-user support

## CDK Constructs Used
API Gateway, Lambda (6+ functions), DynamoDB (GSIs, TTL), SQS (with DLQ), Step Functions, EventBridge, SES, S3, CloudWatch Alarms, IAM, SSM Parameter Store, Cognito (later)
