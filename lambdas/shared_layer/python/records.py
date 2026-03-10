# lambdas/shared/records.py

RECORD_TYPES = {
    "best_sleep_score": {"label": "Best sleep score", "higher_is_better": True},
    "highest_steps": {"label": "Highest step day", "higher_is_better": True},
    "best_fitness_score": {"label": "Best fitness score", "higher_is_better": True},
    "lowest_rhr": {"label": "Lowest resting HR", "higher_is_better": False},
    "highest_hrv": {"label": "Highest HRV", "higher_is_better": True},
}


def check_records(
    current_records: dict[str, dict],
    this_week: dict[str, float],
) -> dict:
    """Check if any records were broken or nearly broken this week.

    Args:
        current_records: {record_type: {"value": float, "date": str}}
        this_week: {record_type: best_value_this_week}

    Returns:
        {record_type: {"broken": bool, "close": bool, ...}}
    """
    result = {}
    for rec_type, config in RECORD_TYPES.items():
        if rec_type not in this_week:
            continue

        week_val = this_week[rec_type]
        current = current_records.get(rec_type, {})
        current_val = current.get("value")

        if current_val is None:
            # First record
            result[rec_type] = {
                "broken": True,
                "close": False,
                "old_value": None,
                "new_value": week_val,
            }
            continue

        higher_better = config["higher_is_better"]
        is_broken = (week_val > current_val) if higher_better else (week_val < current_val)

        # "Close" = within 5% of record
        if current_val != 0:
            pct_diff = abs(week_val - current_val) / abs(current_val)
            is_close = pct_diff <= 0.05 and not is_broken
        else:
            is_close = False

        result[rec_type] = {
            "broken": is_broken,
            "close": is_close,
            "value": current_val,
            "date": current.get("date", ""),
            "new_value": week_val if is_broken else None,
            "this_week": week_val,
        }

    return result


def format_records(records_status: dict) -> list[str]:
    """Format records for email display.

    Only shows records that were broken or close to being broken.
    """
    lines = []
    for rec_type, status in records_status.items():
        config = RECORD_TYPES.get(rec_type, {})
        label = config.get("label", rec_type)

        if status.get("broken"):
            old = status.get("old_value")
            new = status.get("new_value")
            if old is not None:
                lines.append(f"🎉 NEW RECORD: {label}: {new} (prev: {old})")
            else:
                lines.append(f"📈 {label}: {new}")
        elif status.get("close"):
            val = status.get("value")
            this = status.get("this_week")
            lines.append(f"📈 {label}: {val} (you hit {this} — so close!)")

    return lines
