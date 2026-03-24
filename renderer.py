"""
Roster renderer: generates HTML output and terminal summary.

Outputs:
  - roster.html: colour-coded grid showing all 4 weeks
  - Terminal summary: hours per worker, weekend off count, constraint info
"""

import json
from validator import get_worker_stats, get_coverage_gaps

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_ABBR = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Display order: Monday first, Sunday last
DAY_ORDER = [1, 2, 3, 4, 5, 6, 0]  # Mon=1 … Sat=6, Sun=0
DAY_ORDER_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Colour scheme for workers
WORKER_COLORS = {
    "Worker A": {"bg": "#4A90D9", "text": "#FFFFFF"},
    "Worker B": {"bg": "#E67E22", "text": "#FFFFFF"},
    "Worker C": {"bg": "#27AE60", "text": "#FFFFFF"},
    "Worker D": {"bg": "#8E44AD", "text": "#FFFFFF"},
}

ROLE_LABELS = {
    "P": "Days (Sun/Wed) + Early weekends",
    "WO2": "Evenings (Mon-Thu) \u2014 Sat+Sun off",
    "Q": "Sun evening + Thu day + Mid weekends",
    "R": "Days (Mon/Tue) + Late weekends",
}


def render_html(roster, validation_result, output_path="roster.html"):
    """Generate a formatted HTML file with the roster grid."""
    stats = get_worker_stats(roster)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>4-Week Rotating Roster</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 20px;
  }}
  h1 {{
    text-align: center;
    color: #ffffff;
    margin-bottom: 8px;
    font-size: 1.8em;
  }}
  .subtitle {{
    text-align: center;
    color: #a0a0b0;
    margin-bottom: 24px;
    font-size: 0.95em;
  }}
  .week-container {{
    margin-bottom: 28px;
    background: #16213e;
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  }}
  .week-header {{
    font-size: 1.2em;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a2a4a;
  }}
  .week-header .roles {{
    font-size: 0.75em;
    font-weight: 400;
    color: #8888aa;
    margin-top: 4px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  th {{
    background: #0f3460;
    color: #e0e0e0;
    padding: 8px 4px;
    font-size: 0.85em;
    font-weight: 600;
    border: 1px solid #1a1a3e;
  }}
  td {{
    padding: 6px;
    border: 1px solid #1a1a3e;
    vertical-align: middle;
    font-size: 0.85em;
  }}
  .shift-block {{
    border-radius: 4px;
    padding: 3px 5px;
    margin-bottom: 2px;
    font-size: 0.9em;
    line-height: 1.3;
  }}
  .shift-time {{
    font-weight: 700;
  }}
  .shift-duration {{
    font-weight: 400;
    opacity: 0.85;
  }}
  .summary-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 16px;
  }}
  .summary-table th, .summary-table td {{
    padding: 8px 12px;
    border: 1px solid #2a2a4a;
    text-align: center;
    height: auto;
  }}
  .summary-table th {{
    background: #0f3460;
  }}
  .summary-section {{
    background: #16213e;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  }}
  .summary-section h2 {{
    color: #ffffff;
    margin-bottom: 12px;
    font-size: 1.1em;
  }}
  .legend {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 20px;
    justify-content: center;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.9em;
  }}
  .legend-color {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
  }}
  .coverage-note {{
    background: #1e3a1e;
    border: 1px solid #2d5a2d;
    border-radius: 6px;
    padding: 10px 14px;
    margin-top: 12px;
    font-size: 0.85em;
    color: #90c090;
  }}
  .violation {{
    background: #3a1e1e;
    border: 1px solid #5a2d2d;
    color: #c09090;
  }}
</style>
</head>
<body>
<h1>4-Week Rotating Roster</h1>
<p class="subtitle">4 workers &middot; 40 hours/week each &middot; Coverage: Sun-Thu 0400-0200, Fri-Sat 0400-0400</p>

<div class="legend">
"""

    for worker, colors in WORKER_COLORS.items():
        html += f'  <div class="legend-item"><div class="legend-color" style="background:{colors["bg"]}"></div>{worker}</div>\n'

    html += "</div>\n\n"

    # Render each week as a compact worker-per-row table
    for week_data in roster["weeks"]:
        wk = week_data["week_number"]
        roles = week_data.get("worker_roles", {})
        role_str = ", ".join(f"{w.replace('Worker ', '')}: {r}" for w, r in roles.items())

        html += f'<div class="week-container">\n'
        html += f'  <div class="week-header">Week {wk}'
        html += f'<div class="roles">Roles: {role_str}</div></div>\n'
        html += "  <table>\n    <tr>\n"

        # Header row: Worker | Mon | Tue | Wed | Thu | Fri | Sat | Sun
        html += '      <th style="width:90px">Worker</th>\n'
        for abbr in DAY_ORDER_ABBR:
            html += f"      <th>{abbr}</th>\n"
        html += "    </tr>\n"

        # One row per worker
        for worker in roster["workers"]:
            colors = WORKER_COLORS.get(worker, {"bg": "#555", "text": "#fff"})
            worker_label = worker.replace("Worker ", "")
            html += f'    <tr>\n'
            html += (
                f'      <td style="background:{colors["bg"]};color:{colors["text"]};'
                f'font-weight:700;text-align:center">{worker_label}</td>\n'
            )

            for day_idx in DAY_ORDER:
                day_shifts = sorted(
                    [s for s in week_data["shifts"]
                     if s["worker"] == worker and s["day_index"] == day_idx],
                    key=lambda s: s["start_hour"],
                )
                if day_shifts:
                    cell_lines = "".join(
                        f'<div class="shift-block" style="background:{colors["bg"]}33;'
                        f'color:#e0e0e0;border-left:3px solid {colors["bg"]}">'
                        f'{s["start_time"]}–{s["end_time"]}'
                        f'<span class="shift-duration"> ({s["duration"]}h)</span>'
                        f'</div>'
                        for s in day_shifts
                    )
                    html += f"      <td>{cell_lines}</td>\n"
                else:
                    html += '      <td style="color:#444;text-align:center">—</td>\n'

            html += "    </tr>\n"

        html += "  </table>\n</div>\n\n"

    # Summary section
    html += '<div class="summary-section">\n  <h2>Worker Summary (4-Week Cycle)</h2>\n'
    html += '  <table class="summary-table">\n    <tr>\n'
    html += "      <th>Worker</th><th>Wk 1</th><th>Wk 2</th><th>Wk 3</th><th>Wk 4</th>"
    html += "<th>Total</th><th>Weekends Off</th><th>Consecutive Days Off</th>\n    </tr>\n"

    for worker in roster["workers"]:
        s = stats[worker]
        html += f"    <tr>\n      <td><strong>{worker}</strong></td>"
        for h in s["weekly_hours"]:
            html += f"<td>{h}h</td>"
        html += f'<td><strong>{s["total_hours"]}h</strong></td>'
        html += f'<td>{s["weekends_off"]}/4</td>'
        html += f'<td>{s["consecutive_off_weeks"]}/4</td>'
        html += "\n    </tr>\n"

    html += "  </table>\n"

    # Validation notes
    if validation_result.is_valid:
        html += '  <div class="coverage-note">All hard constraints satisfied. Schedule is valid.</div>\n'
    else:
        html += '  <div class="coverage-note violation">HARD CONSTRAINT VIOLATIONS FOUND:<br>'
        for v in validation_result.hard_violations:
            html += f"&bull; {v}<br>"
        html += "</div>\n"

    if validation_result.soft_violations:
        html += '  <div class="coverage-note" style="background:#2a2a1e;border-color:#4a4a2d;color:#c0c090">'
        html += "Soft constraint notes:<br>"
        for v in validation_result.soft_violations:
            html += f"&bull; {v}<br>"
        html += "</div>\n"

    html += "</div>\n\n</body>\n</html>"

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def print_terminal_summary(roster, validation_result):
    """Print a formatted terminal summary."""
    stats = get_worker_stats(roster)

    print("\n" + "=" * 72)
    print("  4-WEEK ROTATING ROSTER SUMMARY")
    print("=" * 72)

    # Weekly schedule overview
    for week_data in roster["weeks"]:
        wk = week_data["week_number"]
        roles = week_data.get("worker_roles", {})
        print(f"\n--- Week {wk} ---")
        for day_idx in range(7):
            day_shifts = sorted(
                [s for s in week_data["shifts"] if s["day_index"] == day_idx],
                key=lambda s: s["start_hour"]
            )
            if day_shifts:
                shift_strs = []
                for s in day_shifts:
                    worker_label = s["worker"].replace("Worker ", "")
                    shift_strs.append(
                        f"{worker_label}: {s['start_time']}-{s['end_time']} ({s['duration']}h)"
                    )
                print(f"  {DAY_ABBR[day_idx]:>3}: {' | '.join(shift_strs)}")
            else:
                print(f"  {DAY_ABBR[day_idx]:>3}: (no shifts)")

    # Hours per worker
    print("\n" + "-" * 72)
    print("  HOURS PER WORKER")
    print("-" * 72)
    header = f"  {'Worker':<12}"
    for i in range(4):
        header += f"{'Wk'+str(i+1):>8}"
    header += f"{'Total':>10}"
    print(header)

    for worker in roster["workers"]:
        s = stats[worker]
        row = f"  {worker:<12}"
        for h in s["weekly_hours"]:
            row += f"{h:>7}h"
        row += f"{s['total_hours']:>9}h"
        print(row)

    # Soft constraints
    print("\n" + "-" * 72)
    print("  SOFT CONSTRAINTS")
    print("-" * 72)
    for worker in roster["workers"]:
        s = stats[worker]
        print(
            f"  {worker}: {s['weekends_off']}/4 weekends off, "
            f"{s['consecutive_off_weeks']}/4 weeks with consecutive days off"
        )

    # Coverage gaps
    print("\n" + "-" * 72)
    print("  COVERAGE & CONSTRAINT CHECK")
    print("-" * 72)

    if validation_result.is_valid:
        print("  [PASS] All hard constraints satisfied")
    else:
        print(f"  [FAIL] {len(validation_result.hard_violations)} hard violation(s):")
        for v in validation_result.hard_violations:
            print(f"    - {v}")

    if validation_result.soft_violations:
        print(f"\n  Soft constraint violations ({len(validation_result.soft_violations)}):")
        for v in validation_result.soft_violations:
            print(f"    - {v}")

    if validation_result.soft_satisfied:
        satisfied_count = len([s for s in validation_result.soft_satisfied
                              if "weekend" in s.lower() or "consecutive" in s.lower()])
        print(f"\n  Soft constraints met: {satisfied_count} items")

    # Coverage check per week
    for week_data in roster["weeks"]:
        gaps = get_coverage_gaps(week_data)
        wk = week_data["week_number"]
        if gaps:
            print(f"  [GAP] Week {wk}: {len(gaps)} uncovered hour(s)")
            for day, hour in gaps[:5]:
                print(f"    - {day} {hour}")
            if len(gaps) > 5:
                print(f"    ... and {len(gaps)-5} more")
        else:
            print(f"  [OK] Week {wk}: Full coverage confirmed")

    print("\n" + "=" * 72)
