from datetime import date, timedelta

DAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _fmt_date_range(start: str, end: str) -> str:
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if s.month == e.month:
            return f"{months[s.month-1]} {s.day} – {e.day}, {s.year}"
        return f"{months[s.month-1]} {s.day} – {months[e.month-1]} {e.day}, {e.year}"
    except (ValueError, IndexError):
        return f"{start} to {end}"


def _day_label(d: str) -> str:
    """Format as 'Mon (03/03)'."""
    dt = date.fromisoformat(d)
    return f"{DAY_ABBREVS[dt.weekday()]} ({dt.strftime('%m/%d')})"


def format_hours_minutes(hours: float | None) -> str:
    if hours is None:
        return "—"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}m"


def format_steps(steps: float | None) -> str:
    if steps is None:
        return "—"
    if steps >= 10000:
        return f"{steps/1000:.0f}k"
    return f"{steps/1000:.1f}k"


def _wow_text(current: float | None, prior: float | None) -> str:
    if current is None or prior is None:
        return ""
    diff = round(current - prior)
    if abs(diff) <= 1:
        return " (steady)"
    arrow = "↑" if diff > 0 else "↓"
    return f" ({arrow}{abs(diff)})"


def _score_color(score: float) -> str:
    if score >= 80:
        return "#22c55e"
    elif score >= 60:
        return "#eab308"
    return "#ef4444"


def _grade_color(grade: str) -> str:
    if grade in ("A+", "A", "A-"):
        return "#22c55e"
    elif grade in ("B+", "B", "B-"):
        return "#eab308"
    return "#ef4444"


def render_score_bar(score: float) -> str:
    """Render an HTML progress bar for a score 0-100."""
    pct = max(0, min(100, round(score)))
    color = _score_color(score)
    remainder = 100 - pct
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:4px;">'
        f'<tr>'
        f'<td style="width:{pct}%;background-color:{color};height:8px;'
        f'border-radius:4px 0 0 4px;"></td>'
        f'<td style="width:{remainder}%;background-color:#e5e7eb;height:8px;'
        f'border-radius:0 4px 4px 0;"></td>'
        f'</tr></table>'
    )


def _card(title: str, content: str, accent_color: str = "#6366f1") -> str:
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-bottom:16px;">'
        f'<tr><td style="background-color:#ffffff;border:1px solid #e5e7eb;'
        f'border-radius:8px;padding:0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<tr><td style="padding:16px 20px 12px 20px;border-bottom:1px solid #e5e7eb;'
        f'border-left:4px solid {accent_color};border-radius:8px 0 0 0;">'
        f'<span style="font-size:16px;font-weight:bold;color:#111827;">{title}</span>'
        f'</td></tr>'
        f'<tr><td style="padding:16px 20px 20px 20px;">{content}</td></tr>'
        f'</table>'
        f'</td></tr></table>'
    )


def _stat_row(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:4px 0;color:#6b7280;font-size:14px;">{label}</td>'
        f'<td style="padding:4px 0;color:#111827;font-size:14px;text-align:right;'
        f'font-weight:600;">{value}</td></tr>'
    )


def _daily_score_row(day_label: str, score: float | None) -> str:
    if score is not None:
        color = _score_color(score)
        score_str = f'<span style="color:{color};font-weight:700;">{score:.0f}</span>'
    else:
        score_str = '<span style="color:#9ca3af;">—</span>'
    return (
        f'<tr><td style="padding:3px 0;color:#6b7280;font-size:13px;">{day_label}</td>'
        f'<td style="padding:3px 0;text-align:right;font-size:13px;">{score_str}</td></tr>'
    )


def _insight_block(text: str) -> str:
    if not text:
        return ""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:12px;">'
        f'<tr><td style="padding:10px 14px;background-color:#f5f5f5;'
        f'border-left:3px solid #6366f1;border-radius:0 4px 4px 0;'
        f'font-size:13px;color:#374151;font-style:italic;">{text}</td></tr></table>'
    )


# ─────────────────────────────────────────────

def render_weekly_scores(data: dict, prior_week: dict | None) -> str:
    scores = [
        ("Sleep", data.get("sleep", {}).get("avg_score"), prior_week.get("sleep", {}).get("avg_score") if prior_week else None),
        ("Fitness", data.get("fitness", {}).get("score"), prior_week.get("fitness", {}).get("score") if prior_week else None),
        ("Recovery", data.get("recovery", {}).get("avg_score"), prior_week.get("recovery", {}).get("avg_score") if prior_week else None),
        ("Consistency", data.get("consistency", {}).get("score"), prior_week.get("consistency", {}).get("score") if prior_week else None),
        ("Cardio", data.get("cardio", {}).get("score"), prior_week.get("cardio", {}).get("score") if prior_week else None),
    ]

    rows = ""
    for name, score, prior in scores:
        s = score if score is not None else 0
        color = _score_color(s)
        wow = _wow_text(score, prior)
        wow_html = f'<span style="font-size:11px;color:#6b7280;">{wow}</span>' if wow else ""
        bar = render_score_bar(s)
        rows += (
            f'<tr><td style="padding:8px 0;vertical-align:top;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f'<tr>'
            f'<td style="font-size:14px;color:#111827;font-weight:500;width:100px;">{name}</td>'
            f'<td style="font-size:20px;font-weight:700;color:{color};text-align:right;width:60px;">'
            f'{s:.0f}</td>'
            f'</tr>'
            f'<tr><td colspan="2">{bar}</td></tr>'
            f'<tr><td colspan="2" style="text-align:right;">{wow_html}</td></tr>'
            f'</table>'
            f'</td></tr>'
        )

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{rows}</table>'
    )
    return _card("Your Scores", content)


def render_sleep_section(data: dict) -> str:
    sleep = data.get("sleep", {})
    details = sleep.get("details", {})
    daily = sleep.get("daily_scores", {})
    nights = sleep.get("nights_tracked", 0)

    if nights < 3:
        return ""

    dates = sorted(daily.keys())

    daily_rows = ""
    for d in dates:
        score = daily.get(d)
        daily_rows += _daily_score_row(_day_label(d), score)

    tracked = f" ({nights}/7 nights)" if nights < 7 else ""
    avg_score = sleep.get('avg_score', 0)
    avg_color = _score_color(avg_score)
    daily_rows += (
        f'<tr><td style="padding:6px 0 0 0;font-size:13px;font-weight:700;color:#111827;'
        f'border-top:1px solid #e5e7eb;">Average{tracked}</td>'
        f'<td style="padding:6px 0 0 0;text-align:right;font-size:13px;font-weight:700;'
        f'color:{avg_color};border-top:1px solid #e5e7eb;">{avg_score:.0f}</td></tr>'
    )

    daily_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{daily_rows}</table>'
    )

    # Stats
    stats = ""
    stats += _stat_row("Avg sleep", format_hours_minutes(details.get("avg_total_sleep")))
    stats += _stat_row("Avg deep", format_hours_minutes(details.get("avg_deep")))
    stats += _stat_row("Avg REM", format_hours_minutes(details.get("avg_rem")))
    eff = details.get("avg_efficiency")
    if eff:
        stats += _stat_row("Efficiency", f"{eff:.0f}%")

    best = details.get("best_night")
    worst = details.get("worst_night")
    if best:
        stats += _stat_row("Best night", f"{_day_label(best)} ({daily.get(best, 0):.0f})")
    if worst:
        stats += _stat_row("Worst night", f"{_day_label(worst)} ({daily.get(worst, 0):.0f})")

    stats_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:12px;">{stats}</table>'
    )

    insight = data.get("insights", {}).get("sleep_insight", "")
    insight_html = _insight_block(insight)

    return _card("Sleep", daily_table + stats_table + insight_html, "#6366f1")


def render_fitness_section(data: dict) -> str:
    fitness = data.get("fitness", {})
    steps_by_day = fitness.get("steps_by_day", {})

    if not steps_by_day:
        return ""

    dates = sorted(steps_by_day.keys())
    workouts_by_day = fitness.get("workouts_by_day", {})
    workout_days = fitness.get("workout_days", 0)

    # Steps with bars — scale relative to 10k goal
    step_goal = 10000
    step_rows = ""
    for d in dates:
        s = steps_by_day.get(d)
        if s is not None and s > 0:
            pct = min(100, round(s / step_goal * 100))
            color = "#22c55e" if s >= step_goal else ("#eab308" if s >= 5000 else "#ef4444")
            bar = (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-collapse:collapse;margin-top:2px;">'
                f'<tr><td style="width:{pct}%;background-color:{color};height:6px;'
                f'border-radius:3px 0 0 3px;"></td>'
                f'<td style="width:{100-pct}%;background-color:#e5e7eb;height:6px;'
                f'border-radius:0 3px 3px 0;"></td></tr></table>'
            )
            step_str = format_steps(s)
        else:
            bar = ""
            step_str = "—"
        step_rows += (
            f'<tr><td style="padding:4px 0 2px 0;vertical-align:bottom;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f'<tr>'
            f'<td style="color:#6b7280;font-size:13px;width:100px;">{_day_label(d)}</td>'
            f'<td style="text-align:right;color:#111827;font-size:13px;font-weight:600;'
            f'width:50px;">{step_str}</td>'
            f'</tr>'
            f'<tr><td colspan="2">{bar}</td></tr>'
            f'</table></td></tr>'
        )
    avg_steps = fitness.get("avg_steps", 0)
    step_rows += (
        f'<tr><td style="padding:8px 0 0 0;font-size:13px;font-weight:700;color:#111827;'
        f'border-top:1px solid #e5e7eb;">'
        f'Average: {avg_steps:,.0f} steps/day</td></tr>'
    )

    steps_html = (
        f'<div style="margin-bottom:12px;">'
        f'<span style="font-size:13px;font-weight:600;color:#6b7280;'
        f'text-transform:uppercase;letter-spacing:0.5px;">Steps</span>'
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:4px;">{step_rows}</table></div>'
    )

    # Workouts
    total_cal = fitness.get("total_calories", 0)
    workout_header = (
        f'<div style="margin-top:8px;">'
        f'<span style="font-size:13px;font-weight:600;color:#6b7280;'
        f'text-transform:uppercase;letter-spacing:0.5px;">'
        f'Workouts — {workout_days}/7 days, {total_cal:,.0f} kcal total</span>'
    )

    workout_rows = ""
    if workouts_by_day:
        # Find max day calories for bar scaling
        day_cals = {}
        for d in dates:
            dw = workouts_by_day.get(d)
            if dw:
                day_cals[d] = sum(w["calories"] for w in dw)
        max_cal = max(day_cals.values()) if day_cals else 1

        best_day_cal = 0
        best_day_name = None
        for d in dates:
            day_workouts = workouts_by_day.get(d)
            day_name = _day_label(d)
            if not day_workouts:
                # Rest day — empty gray bar with "Rest" label
                workout_rows += (
                    f'<tr><td style="padding:4px 0 2px 0;">'
                    f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
                    f'<tr>'
                    f'<td style="color:#9ca3af;font-size:13px;">{day_name}</td>'
                    f'<td style="text-align:right;color:#9ca3af;font-size:12px;font-style:italic;">Rest</td>'
                    f'</tr>'
                    f'<tr><td colspan="2">'
                    f'<table width="100%" cellpadding="0" cellspacing="0" '
                    f'style="border-collapse:collapse;margin-top:2px;">'
                    f'<tr><td style="width:100%;background-color:#e5e7eb;height:4px;'
                    f'border-radius:2px;"></td></tr></table>'
                    f'</td></tr>'
                    f'</table></td></tr>'
                )
                continue
            day_cal = day_cals[d]
            pct = min(100, round(day_cal / max_cal * 100))

            # Bar for the day
            bar = (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-collapse:collapse;margin-top:2px;">'
                f'<tr><td style="width:{pct}%;background-color:#22c55e;height:6px;'
                f'border-radius:3px 0 0 3px;"></td>'
                f'<td style="width:{100-pct}%;background-color:#e5e7eb;height:6px;'
                f'border-radius:0 3px 3px 0;"></td></tr></table>'
            )

            # Workout details below bar
            detail_parts = []
            for w in day_workouts:
                hr_str = f" · HR {w['avg_hr']:.0f}" if w.get("avg_hr") else ""
                detail_parts.append(
                    f'{w["name"]} ({w["duration"]:.0f}m, {w["calories"]:.0f} cal{hr_str})'
                )
            details_str = " &nbsp;+&nbsp; ".join(detail_parts)

            workout_rows += (
                f'<tr><td style="padding:6px 0 2px 0;">'
                f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
                f'<tr>'
                f'<td style="color:#111827;font-size:13px;font-weight:600;">{day_name}</td>'
                f'<td style="text-align:right;color:#111827;font-size:13px;font-weight:600;">'
                f'{day_cal:.0f} cal</td>'
                f'</tr>'
                f'<tr><td colspan="2">{bar}</td></tr>'
                f'<tr><td colspan="2" style="padding-top:2px;color:#6b7280;font-size:12px;">'
                f'{details_str}</td></tr>'
                f'</table></td></tr>'
            )

            if day_cal > best_day_cal:
                best_day_cal = day_cal
                best_day_name = day_name

        if best_day_name:
            workout_rows += (
                f'<tr><td style="padding:8px 0 0 0;font-size:12px;color:#6b7280;'
                f'border-top:1px solid #e5e7eb;">'
                f'Best day: <span style="font-weight:600;color:#22c55e;">'
                f'{best_day_name} — {best_day_cal:.0f} cal</span></td></tr>'
            )
    else:
        workout_rows = (
            f'<tr><td style="padding:3px 0;color:#9ca3af;font-size:13px;font-style:italic;">'
            f'Rest week — no workouts logged</td></tr>'
        )

    workouts_html = (
        workout_header +
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:8px;">{workout_rows}</table></div>'
    )

    return _card("Fitness", steps_html + workouts_html, "#22c55e")


def render_recovery_section(data: dict) -> str:
    recovery = data.get("recovery", {})
    daily = recovery.get("daily_scores", {})

    if not daily or all(v is None for v in daily.values()):
        return ""

    dates = sorted(daily.keys())

    daily_rows = ""
    for d in dates:
        score = daily.get(d)
        daily_rows += _daily_score_row(_day_label(d), score)

    avg = recovery.get("avg_score")
    if avg:
        avg_color = _score_color(avg)
        daily_rows += (
            f'<tr><td style="padding:6px 0 0 0;font-size:13px;font-weight:700;color:#111827;'
            f'border-top:1px solid #e5e7eb;">Average</td>'
            f'<td style="padding:6px 0 0 0;text-align:right;font-size:13px;font-weight:700;'
            f'color:{avg_color};border-top:1px solid #e5e7eb;">{avg:.0f}</td></tr>'
        )

    daily_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{daily_rows}</table>'
    )

    # Vitals
    rhr = recovery.get("rhr_avg")
    hrv = recovery.get("hrv_avg")
    resp = recovery.get("resp_avg")
    walk = recovery.get("walk_hr_avg")
    baselines = data.get("baselines", {})

    stats = ""
    if rhr:
        bl = baselines.get('rhr_avg')
        bl_str = f" (30d avg: {bl:.0f})" if bl else ""
        stats += _stat_row("Resting HR", f"{rhr:.0f} bpm{bl_str}")
    if hrv:
        bl = baselines.get('hrv_avg')
        bl_str = f" (30d avg: {bl:.0f})" if bl else ""
        stats += _stat_row("HRV", f"{hrv:.0f} ms{bl_str}")
    if resp:
        stats += _stat_row("Resp rate", f"{resp:.1f} breaths/min")
    if walk:
        stats += _stat_row("Walking HR", f"{walk:.0f} bpm")

    verdict = recovery.get("verdict", "STEADY")
    verdict_color = "#22c55e" if verdict == "IMPROVING" else ("#ef4444" if verdict == "DECLINING" else "#eab308")
    stats += (
        f'<tr><td style="padding:8px 0 0 0;font-size:13px;font-weight:700;color:#111827;'
        f'border-top:1px solid #e5e7eb;">Verdict</td>'
        f'<td style="padding:8px 0 0 0;text-align:right;font-size:13px;font-weight:700;'
        f'color:{verdict_color};border-top:1px solid #e5e7eb;">{verdict}</td></tr>'
    )

    stats_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:12px;">{stats}</table>'
    )

    return _card("Recovery", daily_table + stats_table, "#f59e0b")


def render_consistency_section(data: dict) -> str:
    c = data.get("consistency", {})
    if c.get("score") is None:
        return ""

    stats = ""
    stats += _stat_row("Bedtime spread", f"±{c.get('bedtime_std_min', 0):.0f} min")
    stats += _stat_row("Step variability", f"CV {c.get('step_cv', 0):.0f}%")
    stats += _stat_row("Workout days", f"{c.get('workout_count', 0)}/7")
    stats += _stat_row("Sleep range", format_hours_minutes(c.get("sleep_range_hours")))

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{stats}</table>'
    )
    return _card("Consistency", content, "#8b5cf6")


def render_cardio_section(data: dict) -> str:
    cardio = data.get("cardio", {})

    if cardio.get("rhr_avg") is None:
        return ""

    rhr_trend = cardio.get("rhr_trend", 0)
    rhr_dir = "↓ improving" if rhr_trend < -0.1 else ("↑ watch" if rhr_trend > 0.1 else "stable")

    stats = ""
    stats += _stat_row("Resting HR", f"{cardio['rhr_avg']:.0f} bpm ({rhr_dir})")

    if cardio.get("walk_hr_avg"):
        stats += _stat_row("Walking HR", f"{cardio['walk_hr_avg']:.0f} bpm")

    hrv_trend = cardio.get("hrv_trend", 0)
    hrv_dir = "↑ good" if hrv_trend > 0.1 else ("↓ watch" if hrv_trend < -0.1 else "stable")
    if cardio.get("hrv_avg"):
        stats += _stat_row("HRV trend", hrv_dir)

    if cardio.get("resp_avg"):
        stats += _stat_row("Resp rate", f"{cardio['resp_avg']:.1f} breaths/min")

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{stats}</table>'
    )
    return _card("Cardio", content, "#ef4444")


def render_correlations_section(data: dict) -> str:
    corr = data.get("correlations", {})
    if not corr:
        return ""

    items = []

    ws = corr.get("workout_sleep", {})
    if ws.get("significant") and ws["difference_min"] > 0:
        items.append(f"Workout days → +{ws['difference_min']:.0f}m deep sleep")

    bs = corr.get("bedtime_sleep", {})
    if bs:
        before = bs.get("before_midnight", {})
        after = bs.get("after_1am", {})
        if before.get("count", 0) >= 3 and after.get("count", 0) >= 3:
            diff = before["avg_score"] - after["avg_score"]
            if diff > 10:
                items.append(f"Early bedtime → +{diff:.0f} sleep score")

    dow = corr.get("day_of_week", {})
    if dow.get("best_day") and dow.get("worst_day"):
        best = dow['best_day']
        worst = dow['worst_day']
        b_avg = dow['averages'].get(best, '?')
        w_avg = dow['averages'].get(worst, '?')
        items.append(f"Best sleep day: {best} (avg {b_avg})")
        items.append(f"Worst sleep day: {worst} (avg {w_avg})")

    if not items:
        return ""

    rows = ""
    for item in items:
        rows += (
            f'<tr><td style="padding:4px 0;color:#111827;font-size:14px;">'
            f'<span style="color:#6366f1;margin-right:6px;">&#8226;</span>{item}</td></tr>'
        )

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{rows}</table>'
    )
    return _card("Patterns", content, "#6366f1")


def render_anomalies_section(data: dict) -> str:
    anomalies = data.get("anomalies", [])
    baselines = data.get("baselines", {})

    if baselines.get("history_days", 0) < 14:
        return ""

    if not anomalies:
        content = (
            '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            '<tr><td style="padding:4px 0;color:#22c55e;font-size:14px;">'
            '&#10003; All clear — metrics in normal range.</td></tr></table>'
        )
    else:
        rows = ""
        for a in anomalies:
            metric_label = a["metric"].replace("_", " ").title()
            rows += (
                f'<tr><td style="padding:4px 0;color:#ef4444;font-size:14px;">'
                f'&#9888; {metric_label}: {a["deviation"]} std devs from baseline'
                f' ({a["baseline_avg"]:.1f}) for {a["days"]} days</td></tr>'
            )
        content = (
            f'<table width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;">{rows}</table>'
        )

    return _card("Anomalies", content, "#f97316")


def render_focus_section(data: dict) -> str:
    focus = data.get("insights", {}).get("weekly_focus", "")

    if focus:
        text = focus.replace("\n", "<br>")
    else:
        text = "Keep doing what you're doing!"

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<tr><td style="padding:8px 14px;background-color:#f0f0ff;border-radius:6px;'
        f'font-size:14px;color:#111827;line-height:1.6;">{text}</td></tr></table>'
    )
    return _card("This Week's Focus", content, "#6366f1")


def render_records_section(data: dict) -> str:
    records = data.get("records", {})
    this_week = records.get("this_week", {})

    if not this_week:
        return ""

    labels = {
        "best_sleep_score": "Best Sleep Score",
        "highest_steps": "Highest Steps",
        "best_fitness_score": "Fitness Score",
        "lowest_rhr": "Lowest Resting HR",
        "highest_hrv": "Highest HRV",
    }

    rows = ""
    for key, val in this_week.items():
        label = labels.get(key, key.replace("_", " ").title())
        if isinstance(val, float):
            if "steps" in key:
                val_str = f"{val:,.0f}"
            else:
                val_str = f"{val:.1f}"
        else:
            val_str = str(val)
        rows += _stat_row(label, val_str)

    content = (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{rows}</table>'
    )
    return _card("This Week's Bests", content, "#eab308")


def render_full_email(data: dict, prior_week: dict | None = None) -> tuple[str, str, str]:
    """Render the complete email. Returns (subject, html_body, text_body)."""
    week_start = data.get("week_start", "")
    week_end = data.get("week_end", "")

    sleep_score = data.get("sleep", {}).get("avg_score", 0) or 0
    fitness_score = data.get("fitness", {}).get("score", 0) or 0
    recovery_score = data.get("recovery", {}).get("avg_score", 0) or 0

    overall = data.get("overall", {})
    grade = overall.get("grade", "?")
    avg_score = overall.get("avg_score", 0)

    date_range = _fmt_date_range(week_start, week_end)

    subject = (f"HealthForge {grade}"
               f" — Sleep {sleep_score:.0f}"
               f" | Fitness {fitness_score:.0f}"
               f" | Recovery {recovery_score:.0f}"
               f" ({date_range})")

    # Build section HTML
    sections = [
        render_weekly_scores(data, prior_week),
        render_sleep_section(data),
        render_fitness_section(data),
        render_recovery_section(data),
        render_consistency_section(data),
        render_cardio_section(data),
        render_correlations_section(data),
        render_anomalies_section(data),
        render_focus_section(data),
        render_records_section(data),
    ]
    filtered = [s for s in sections if s]
    sections_html = "\n".join(filtered)

    # Limited data banner
    limited_banner = ""
    if data.get("limited_data"):
        limited_banner = (
            '<table width="100%" cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;margin-bottom:16px;">'
            '<tr><td style="background-color:#fef3c7;border:1px solid #fde68a;'
            'border-radius:8px;padding:12px 16px;font-size:13px;color:#92400e;'
            'text-align:center;">Limited data this week — scores may not be representative.'
            '</td></tr></table>'
        )

    grade_color = _grade_color(grade)
    avg_score_color = _score_color(avg_score)

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background-color:#f5f5f5;">
<tr><td align="center" style="padding:16px 8px;">

<!-- Main container -->
<table width="600" cellpadding="0" cellspacing="0" style="border-collapse:collapse;max-width:600px;width:100%;">

<!-- Hero header -->
<tr><td style="background-color:#1a1a2e;border-radius:12px 12px 0 0;padding:32px 24px 24px 24px;text-align:center;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
<tr><td style="text-align:center;">
<span style="font-size:14px;font-weight:600;color:#6366f1;text-transform:uppercase;letter-spacing:2px;">HealthForge</span>
</td></tr>
<tr><td style="text-align:center;padding-top:20px;">
<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 auto;">
<tr><td style="width:80px;height:80px;border-radius:40px;background-color:{grade_color};text-align:center;vertical-align:middle;">
<span style="font-size:36px;font-weight:800;color:#ffffff;line-height:80px;">{grade}</span>
</td></tr>
</table>
</td></tr>
<tr><td style="text-align:center;padding-top:8px;">
<span style="font-size:16px;color:{avg_score_color};font-weight:600;">{avg_score:.0f}/100</span>
</td></tr>
<tr><td style="text-align:center;padding-top:16px;">
<span style="font-size:13px;color:#9ca3af;">{date_range}</span>
</td></tr>
<tr><td style="text-align:center;padding-top:12px;">
<span style="font-size:18px;color:#e5e7eb;">Hey! Here's your week in review.</span>
</td></tr>
</table>
</td></tr>

<!-- Body area -->
<tr><td style="background-color:#f5f5f5;padding:20px 16px 8px 16px;">
{limited_banner}
{sections_html}
</td></tr>

<!-- Footer -->
<tr><td style="background-color:#1a1a2e;border-radius:0 0 12px 12px;padding:24px;text-align:center;">
<span style="font-size:14px;color:#9ca3af;font-style:italic;">Stay consistent. Small wins compound.</span>
<br>
<span style="font-size:13px;color:#6366f1;font-weight:600;padding-top:8px;display:inline-block;">— HealthForge</span>
</td></tr>

</table>
<!-- End main container -->

</td></tr>
</table>
</body>
</html>"""

    # Plain text fallback
    text_lines = [
        f"HealthForge Weekly Report — {date_range}",
        f"Overall Grade: {grade} ({avg_score:.0f}/100)",
        "",
        f"Sleep: {sleep_score:.0f}  |  Fitness: {fitness_score:.0f}  |  Recovery: {recovery_score:.0f}",
        "",
        "View this email in an HTML-capable client for the full dashboard.",
        "",
        "Stay consistent. Small wins compound.",
        "— HealthForge",
    ]
    if data.get("limited_data"):
        text_lines.insert(0, "Limited data this week — scores may not be representative.\n")

    text_body = "\n".join(text_lines)

    return subject, html_body, text_body
