# Weekly Email Report — Design Spec

## Overview

A single weekly email sent every Sunday at 10 AM covering Sunday–Saturday. Contains 5 health scores, detailed breakdowns, correlations, anomalies, and one actionable focus item. Plain text format (no HTML).

## Email Structure

### Subject Line
```
HealthForge — Week of Mar 2-8 | Sleep 74 ↑ Fitness 81 Recovery 77
```

### Sections (in order)

#### 1. Weekly Scores (always shown if 3+ days of data)

5 scores, each 0-100, with visual bar and week-over-week comparison.

```
🏆 WEEKLY SCORES
─────────────────────────────────────────────────────
Sleep        72  ████████████████░░░░░░░░  ↑3 from last week
Fitness      81  ████████████████████░░░░  steady
Recovery     77  ███████████████████░░░░░  ↓2
Consistency  68  █████████████████░░░░░░░  ↑5
Cardio       83  ████████████████████░░░░  steady

Overall Week: B+ (76)
```

Overall grade mapping:
- A+ (95-100), A (90-94), A- (85-89)
- B+ (80-84), B (75-79), B- (70-74)
- C+ (65-69), C (60-64), C- (55-59)
- D (below 55)

Week-over-week comparison:
- Show ↑/↓ with point difference if prior week exists
- Show "steady" if change is ≤1 point
- Show "—" if no prior week data

#### 2. Sleep Section (needs 3+ nights of data)

```
😴 SLEEP
─────────────────────────────────────────────────────
Sun  Mon  Tue  Wed  Thu  Fri  Sat
 74   82   89   —    58   75   80    avg: 76 (5 of 7 nights)

Total sleep avg: 6h 38m
Deep sleep avg:  58 min (▲12% vs last week)
REM avg:         1h 22m
Efficiency:      88%

Best:  Tuesday (89) — 7h 12m, bedtime 12:15 AM
Worst: Thursday (58) — 4h 06m, bedtime 3:00 AM

Bedtime: avg 12:42 AM | range: 11:50 PM – 3:00 AM
Wake:    avg 7:45 AM

💡 [Gemini-generated sleep insight based on computed patterns]
```

Data sources:
- `sleep_analysis.totalSleep` — total hours (convert to hours:minutes)
- `sleep_analysis.deep` — deep sleep hours
- `sleep_analysis.rem` — REM hours
- `sleep_analysis.core` — core/light sleep hours
- `sleep_analysis.awake` — awake time during sleep
- `sleep_analysis.sleepStart` — bedtime
- `sleep_analysis.sleepEnd` — wake time
- Efficiency = `totalSleep` / (`totalSleep` + `awake`) × 100

#### 3. Fitness Section (needs 3+ days of data)

```
🏃 FITNESS
─────────────────────────────────────────────────────
Active days:     5 / 7
Total calories:  3,240 kcal (↑8% vs last week)
Avg steps:       7,842 / day
Exercise time:   42 min / day avg

Steps by day:
Sun  Mon  Tue  Wed  Thu  Fri  Sat
6.2k 8.4k 9.1k 7.2k 8.8k 6.5k 8.7k

Workouts this week:
• Mon — Elliptical, 35 min, 380 cal, avg HR 156
• Wed — Strength, 45 min, 290 cal, avg HR 132
• Fri — Elliptical, 40 min, 410 cal, avg HR 162

🏆 Top session: Friday Elliptical — 410 cal burned
```

If no workouts: show "Rest week — 0 workouts" and skip workout list and top session.

Data sources:
- `step_count.qty` — daily steps
- `active_energy.qty` — daily active energy in kJ (convert to kcal: ÷ 4.184)
- `apple_exercise_time.qty` — exercise minutes
- `workout` records — name, duration, activeEnergyBurned, avgHeartRate
- Active day = day with `apple_exercise_time` ≥ 30 min

#### 4. Recovery Section (needs 3+ days of data)

```
❤️ RECOVERY
─────────────────────────────────────────────────────
Sun  Mon  Tue  Wed  Thu  Fri  Sat
 81   84   72   65   78   82   80    avg: 77

Resting HR:   58 bpm (30-day avg: 59)
HRV:          44 ms  (30-day avg: 42)  ← improving
Resp rate:    15.2 /min (normal)
Walking HR:   98 bpm (stable)

Recovery verdict: STEADY
You're well-recovered. No red flags.
```

Recovery verdict:
- "PUSH IT" (80+) — ready for high intensity
- "STEADY" (60-79) — normal training
- "RECOVER" (<60) — prioritize rest

Data sources:
- `resting_heart_rate.qty` — RHR in bpm
- `heart_rate_variability.qty` — HRV in ms
- `respiratory_rate.qty` — breaths per min
- `walking_heart_rate_average.qty` — walking HR in bpm
- 30-day averages computed from stored historical data

#### 5. Consistency Section (needs 5+ days of data)

```
📊 CONSISTENCY
─────────────────────────────────────────────────────
Bedtime consistency:  ±34 min (goal: ±30)
Step consistency:     CV 14% (good)
Workout regularity:   3 sessions (on track)
Sleep duration range: 4h 06m – 8h 28m ← wide spread

⚠️ Your sleep duration swung 4+ hours this week.
   Keeping it within 2 hours improves deep sleep by ~18%.
```

Consistency ratings:
- Bedtime: ±15 min = excellent, ±30 = good, ±45 = fair, ±60+ = poor
- Step CV: <10% = excellent, <20% = good, <30% = fair, 30%+ = poor
- Sleep range: <1.5h = excellent, <2h = good, <3h = fair, 3h+ = poor

Data sources:
- Standard deviation of `sleep_analysis.sleepStart` times
- Coefficient of variation of `step_count.qty`
- Count of `workout` records
- Min/max of `sleep_analysis.totalSleep`

#### 6. Cardio Health Section (needs 7+ days of RHR data)

```
🫀 CARDIO HEALTH
─────────────────────────────────────────────────────
Resting HR:    58 bpm — trending ↓ (good)
Walking HR:    98 bpm — stable
HRV trend:     ↑ 4.7% over 30 days
Resp rate:     15.2 /min — normal

Your cardiovascular fitness is improving.
RHR has dropped 2 bpm over the past month.
```

Trends computed by comparing this week's average vs 30-day average:
- >5% better = "improving"
- Within 5% = "stable"
- >5% worse = "declining"

For RHR and walking HR, lower is better.
For HRV, higher is better.

Data sources:
- `resting_heart_rate.qty` — 7-day and 30-day averages
- `walking_heart_rate_average.qty` — 7-day and 30-day averages
- `heart_rate_variability.qty` — 7-day and 30-day averages
- `respiratory_rate.qty` — current week average

#### 7. Correlations & Patterns (needs 4+ weeks of data)

```
🔗 CORRELATIONS & PATTERNS
─────────────────────────────────────────────────────
• Workout days → 22 min more deep sleep on average
• Bedtime before 1 AM → sleep score 18 points higher
• Your worst sleep day is consistently Thursday (4-week avg: 61)
• After strength training, next-day HRV is 8% higher than after cardio

📅 Day-of-week fingerprint (4-week rolling):
Best sleep day:    Tuesday (avg 84)
Worst sleep day:   Thursday (avg 61)
Most active day:   Monday (avg 9,200 steps)
Least active day:  Sunday (avg 5,100 steps)
```

Correlations to compute:
1. Workout day vs non-workout day deep sleep
2. Bedtime buckets (before midnight, midnight-1AM, after 1AM) vs sleep score
3. Day-of-week averages for sleep score and step count
4. Workout type vs next-day HRV change
5. Exercise time vs sleep quality same night

Only show correlations that have:
- Minimum 8 data points per group
- Meaningful difference (>10% or >10 points)

#### 8. Anomalies (needs 2+ weeks of baseline)

```
⚠️ ANOMALIES
─────────────────────────────────────────────────────
None this week. All metrics within normal range. ✓
```

Or if anomaly detected:
```
⚠️ ANOMALIES
─────────────────────────────────────────────────────
Resting HR elevated Thu-Fri (67 bpm vs 58 bpm baseline, 2.1 std devs).
Last time this happened: Feb 12 (resolved after 3 days).
```

Rules:
- Trigger when metric exceeds 2 standard deviations from 30-day baseline
- Must persist for 2+ consecutive days (not single-day spikes)
- Max 3 anomalies shown per email (most severe first)
- Include historical context if same anomaly occurred before
- Metrics monitored: RHR, HRV, respiratory rate, sleep duration, deep sleep

#### 9. This Week's Focus (always shown)

```
🎯 THIS WEEK'S FOCUS
─────────────────────────────────────────────────────
Your biggest opportunity: bedtime consistency.
This week you ranged from 11:50 PM to 3:00 AM.
Try keeping bedtime within a 1-hour window.
Based on your data, consistent bedtimes = +18% deep sleep.
```

Generated by Gemini Flash from computed data. Prompt includes:
- All 5 scores and week-over-week changes
- Top 3 weakest areas
- Correlations found
- Anomalies detected

Gemini is told: "Pick the single most impactful thing to focus on. Be specific and cite the user's own data."

#### 10. Personal Records (always shown)

```
📈 Personal Records
• Longest workout streak: 12 days (current: 8)
• Best sleep score: 92 (Feb 18)
• Highest step day: 12,400 (Feb 22)
```

Track in DynamoDB under `RECORD#<type>` sort keys.
Only show records that were either:
- Broken this week (celebrate!)
- Close to being broken (motivate!)

---

## Score Formulas

### Sleep Score (0-100, per night)

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Duration vs 30-day avg | 25% | 100 if within ±30min, scaled down beyond |
| Efficiency | 25% | `totalSleep / (totalSleep + awake) × 100` |
| Deep sleep vs baseline | 20% | 100 if at or above 30-day avg, scaled |
| REM vs baseline | 15% | 100 if at or above 30-day avg, scaled |
| Bedtime consistency | 10% | 100 if within ±15min of 30-day avg bedtime |
| Restfulness (low awake time) | 5% | 100 if awake < 15min, scaled |

Weekly sleep score = average of daily sleep scores (tracked nights only).

### Fitness Score (0-100, weekly)

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Activity consistency | 30% | Days with ≥30 min exercise / 7 × 100 |
| Active calories vs avg | 25% | This week total / 30-day weekly avg × 100, capped at 120 |
| Step consistency | 20% | 100 − (step CV × 2), min 0 |
| Workout intensity | 15% | Based on avg HR during workouts vs max HR estimate |
| Progressive load | 10% | This week calories / last week calories × 100, capped |

If no workouts: workout intensity = 0, redistribute 15% to activity consistency (30→40%) and calories (25→30%).

### Recovery Score (0-100, daily)

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Last night's sleep score | 35% | Direct from sleep score |
| RHR vs 30-day avg | 25% | 100 if at or below avg, scaled down if above |
| HRV vs 30-day avg | 20% | 100 if at or above avg, scaled down if below |
| Respiratory rate vs baseline | 15% | 100 if at or below avg, scaled down if above |
| 7-day sleep debt | 5% | 100 if avg sleep ≥ 7h, scaled down |

If HRV missing: redistribute 20% to RHR (25→35%) and sleep (35→45%).
If respiratory rate missing: redistribute 15% to RHR (25→32%) and HRV (20→28%).

Weekly recovery score = average of daily recovery scores.

### Consistency Score (0-100, weekly)

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Bedtime consistency | 35% | 100 if std dev ≤15 min, 0 if ≥90 min, linear |
| Sleep duration consistency | 25% | 100 if range ≤1h, 0 if ≥5h, linear |
| Step consistency | 20% | 100 if CV ≤10%, 0 if CV ≥50%, linear |
| Workout regularity | 20% | 100 if 3+ sessions, 66 if 2, 33 if 1, 0 if none |

### Cardio Score (0-100, weekly)

| Component | Weight | Calculation |
|-----------|--------|-------------|
| RHR vs 30-day avg | 30% | 100 if at or below avg, scaled if above |
| HRV vs 30-day avg | 30% | 100 if at or above avg, scaled if below |
| Walking HR vs 30-day avg | 20% | 100 if at or below avg, scaled if above |
| RHR 7-day trend | 10% | 100 if trending down, 50 if flat, 0 if trending up |
| HRV 7-day trend | 10% | 100 if trending up, 50 if flat, 0 if trending down |

---

## Edge Case Handling

### Missing Data Display

```
Data points available    Action
─────────────────────    ──────
7 of 7 days              Full section, all stats
4-6 of 7 days            Full section, note "X of 7 days tracked"
2-3 of 7 days            Simplified section, flag "Limited data"
0-1 of 7 days            Skip section entirely
```

Missing days show "—" in daily breakdowns:
```
Sun  Mon  Tue  Wed  Thu  Fri  Sat
 74   82   —    71   58   75   80    avg: 73 (6 of 7 nights)
```

### Section-Specific Minimums

| Section | Minimum Data Required |
|---------|----------------------|
| Weekly Scores | 3+ days of any data |
| Sleep | 3+ nights of sleep data |
| Fitness | 3+ days of step/energy data |
| Recovery | 3+ days of RHR or HRV data |
| Consistency | 5+ days (need enough data for variance) |
| Cardio Health | 7+ days of RHR data |
| Correlations | 4+ weeks of historical data |
| Anomalies | 2+ weeks of baseline data |
| Focus | Always shown (uses whatever data is available) |
| Personal Records | Always shown (uses all-time data) |

### Score Calculation with Missing Components

When a component's data source is missing, redistribute its weight proportionally to remaining components. Never let a missing metric tank the entire score.

### Email-Level Rules

| Condition | Action |
|-----------|--------|
| 0 days of data this week | Don't send email |
| 1-2 days of data | Send minimal email with disclaimer: "Limited data this week" |
| 3+ days of data | Send full email, mark missing days with "—" |
| First 2 weeks ever | Skip correlations and anomalies sections |
| First 4 weeks ever | Skip correlations section |
| No prior week data | Skip week-over-week comparisons, show "first week" |

### Special Cases

- Sleep data with `totalSleep` < 2 hours: flag as "incomplete", exclude from averages
- Active energy in kJ: convert to kcal by dividing by 4.184
- Bedtime after midnight: treat as same "night" (e.g., 1:30 AM Sunday = Saturday night)
- Multiple workouts same day: list all, combine calories for daily totals

---

## Gemini Flash Integration

Two LLM calls per email:

1. **Sleep/pattern insight** — receives computed sleep stats, correlations, and anomalies. Generates 1-2 line insight for the Sleep section.

2. **Weekly focus** — receives all 5 scores, week-over-week changes, weakest areas, and correlations. Generates 3-4 line actionable focus recommendation.

Prompt guidelines:
- Include only computed summaries, never raw health data
- Tell Gemini to cite the user's own numbers
- Tell Gemini to be specific ("bedtime before 1 AM" not "sleep earlier")
- Max 50 words per insight, 80 words per focus
- If Gemini fails, use template fallback (e.g., "Focus on your lowest score this week: Consistency at 68")

---

## Data Flow

```
EventBridge (Sunday 10 AM)
  → Step Functions
    → Step 1: Aggregation Lambda
        Query DynamoDB for this week (Sun-Sat) + 30-day history
        Compute all 5 scores
        Compute rolling averages, baselines, std devs
        Find correlations (if 4+ weeks)
        Detect anomalies (if 2+ weeks)
        Check personal records
        Output: JSON blob with all computed data
    → Step 2: Insight Lambda
        Send computed summaries to Gemini Flash
        Get sleep insight + weekly focus
        Output: insight strings
    → Step 3: Email Lambda
        Render plain text email from template + computed data + insights
        Apply edge case rules (skip sections, show "—", etc.)
        Send via SES
```
