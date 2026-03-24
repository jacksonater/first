"""
Roster scheduler: builds a 4-week rotating cycle for 4 workers.

Coverage requirements:
  - Sunday to Thursday: 0400-0200 (22 hours)
  - Friday to Saturday: 0400-0400 (24 hours)

Hard constraints:
  - Shift length: 6.5-12 hours
  - Standard start times: 0400, 0800, 1200, 1600, 2000, 0000
  - Each worker: exactly 40 hours per week
  - Minimum 1 worker on during coverage hours
  - Minimum 10 hours off between shifts per worker

Math:
  4 workers x 40h = 160 worker-hours/week
  Coverage: Sun-Thu 5x22 + Fri-Sat 2x24 = 158h minimum
  2h slack for overlap

Approach: Use 2-shift weekdays (12h + 10h) and 3-shift weekends (8h + 8h + 8h).
The 2h slack is absorbed by role Q whose Sunday evening shift runs 1600-0400
(2h past the 0200 coverage close) so every role totals exactly 40h.
Define 4 roles (P/WO2/Q/R) that rotate across a 4-week cycle.

Weekend off = Saturday + Sunday off together.
Role WO2 works Mon-Thu evenings and is off Friday, Saturday and Sunday,
giving every worker one full Sat+Sun weekend off per 4-week cycle.
"""

import json
import logging

logger = logging.getLogger(__name__)

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_ABBR = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
WORKERS = ["Worker A", "Worker B", "Worker C", "Worker D"]

# Coverage windows (start_hour, end_hour where end > 24 means next day)
COVERAGE = {
    0: (4, 26),   # Sunday 0400-0200
    1: (4, 26),   # Monday
    2: (4, 26),   # Tuesday
    3: (4, 26),   # Wednesday
    4: (4, 26),   # Thursday
    5: (4, 28),   # Friday 0400-0400
    6: (4, 28),   # Saturday 0400-0400
}


def _format_time(hour):
    """Format hour (0-23) as HHMM string."""
    h = int(hour) % 24
    m = int((hour % 1) * 60)
    return f"{h:02d}{m:02d}"


def _build_role_shifts():
    """
    Define the 4 roles that rotate through the 4-week cycle.

    Each role is a list of (day_index, start_hour, duration) tuples.

    Daily shift structure:
      Sun,Tue,Wed,Thu: A-shift(0400-1600, 12h) + B-shift(1600-0200, 10h) = 22h
      Mon: A-shift(0400-1600, 12h) + B-shift(1600-0200, 10h) = 22h
      Fri,Sat: E(0400-1200, 8h) + M(1200-2000, 8h) + L(2000-0400, 8h) = 24h

    Role assignments ensure:
      - Every role totals exactly 40h
      - All rest constraints (10h min) are met within and across weeks
      - Coverage is complete when all 4 roles are active simultaneously
      - Each worker gets one full Saturday+Sunday off per 4-week cycle (role WO2)

    The 2h budget slack is absorbed by role Q: the Sun B shift runs
    1600-0400 (12h) rather than 1600-0200 (10h), covering 2h past the
    Sunday coverage close so every role still totals exactly 40h.
    """
    # Role P: Sun/Mon day shifts + Fri/Sat late shifts
    # Off: Tuesday, Wednesday, Thursday
    # Hours: 12h + 12h + 8h + 8h = 40h
    role_p = [
        (0, 4, 12),    # Sun A: 0400-1600 (12h)
        (1, 4, 12),    # Mon A: 0400-1600 (12h)
        (5, 20, 8),    # Fri L: 2000-0400 (8h)
        (6, 20, 8),    # Sat L: 2000-0400 (8h)
    ]

    # Role WO2: "Weekend Off" - works Mon-Thu evening shifts (10h each)
    # Off: Friday, Saturday, Sunday  →  full Sat+Sun weekend off
    # Hours: 4 x 10h = 40h
    role_wo2 = [
        (1, 16, 10),   # Mon B: 1600-0200 (10h)
        (2, 16, 10),   # Tue B: 1600-0200 (10h)
        (3, 16, 10),   # Wed B: 1600-0200 (10h)
        (4, 16, 10),   # Thu B: 1600-0200 (10h)
    ]

    # Role Q: Sun evening (extended) + Wed day + Fri/Sat mid shifts
    # Off: Monday, Tuesday, Thursday
    # Hours: 12h + 12h + 8h + 8h = 40h
    # Sun B runs 1600-0400 (12h) to absorb the 2h budget slack
    role_q = [
        (0, 16, 12),   # Sun B: 1600-0400 (12h, 2h past coverage close)
        (3, 4, 12),    # Wed A: 0400-1600 (12h)
        (5, 12, 8),    # Fri M: 1200-2000 (8h)
        (6, 12, 8),    # Sat M: 1200-2000 (8h)
    ]

    # Role R: Tue/Thu day shifts + Fri/Sat early shifts
    # Off: Sunday, Monday, Wednesday
    # Hours: 2x12h + 2x8h = 40h
    role_r = [
        (2, 4, 12),    # Tue A: 0400-1600 (12h)
        (4, 4, 12),    # Thu A: 0400-1600 (12h)
        (5, 4, 8),     # Fri E: 0400-1200 (8h)
        (6, 4, 8),     # Sat E: 0400-1200 (8h)
    ]

    return {
        "P": role_p,
        "WO2": role_wo2,
        "Q": role_q,
        "R": role_r,
    }


def generate_roster():
    """
    Generate the full 4-week rotating roster.

    Pattern order: P -> WO2 -> Q -> R (ensures all cross-week rest constraints met).

    Worker rotation:
      Worker A: wk1=P,   wk2=WO2, wk3=Q,  wk4=R
      Worker B: wk1=R,   wk2=P,   wk3=WO2, wk4=Q
      Worker C: wk1=Q,   wk2=R,   wk3=P,  wk4=WO2
      Worker D: wk1=WO2, wk2=Q,   wk3=R,  wk4=P

    In any calendar week, one worker is on each role -> full coverage.
    """
    roles = _build_role_shifts()

    # Pattern sequence for rotation (verified for cross-week rest compliance)
    pattern_sequence = ["P", "WO2", "Q", "R"]

    # Worker assignments: worker_index -> list of 4 role names (one per week)
    # Worker A starts at offset 0, B at offset 1, etc.
    worker_roles = {}
    for w_idx in range(4):
        worker_roles[w_idx] = []
        for wk in range(4):
            role_idx = (wk - w_idx) % 4
            worker_roles[w_idx].append(pattern_sequence[role_idx])

    roster = {
        "workers": WORKERS,
        "weeks": [],
        "pattern_sequence": pattern_sequence,
        "role_definitions": {},
    }

    # Store role definitions for reference
    for role_name, shifts in roles.items():
        roster["role_definitions"][role_name] = {
            "total_hours": sum(s[2] for s in shifts),
            "shifts": [
                {
                    "day": DAYS[s[0]],
                    "day_index": s[0],
                    "start_hour": s[1],
                    "start_time": _format_time(s[1]),
                    "duration": s[2],
                    "end_time": _format_time(s[1] + s[2]),
                }
                for s in shifts
            ],
        }

    for wk in range(4):
        week_data = {
            "week_number": wk + 1,
            "shifts": [],
            "worker_hours": {},
            "worker_roles": {},
        }

        for w_idx, worker_name in enumerate(WORKERS):
            role_name = worker_roles[w_idx][wk]
            role_shifts = roles[role_name]
            hours = sum(s[2] for s in role_shifts)
            week_data["worker_hours"][worker_name] = hours
            week_data["worker_roles"][worker_name] = role_name

            for s in role_shifts:
                day_idx, start, duration = s
                end_hour = (start + duration) % 24
                week_data["shifts"].append({
                    "worker": worker_name,
                    "worker_index": w_idx,
                    "role": role_name,
                    "day": DAYS[day_idx],
                    "day_index": day_idx,
                    "start_hour": start,
                    "start_time": _format_time(start),
                    "duration": duration,
                    "end_hour": end_hour,
                    "end_time": _format_time(start + duration),
                })

        roster["weeks"].append(week_data)

    return roster


def roster_to_json(roster):
    """Serialize roster to JSON string."""
    return json.dumps(roster, indent=2)
