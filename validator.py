"""
Roster validator: checks all hard and soft constraints.

Hard constraints (must all pass):
  - Shift length: 6.5-12 hours
  - Standard start times: 0, 4, 8, 12, 16, 20
  - Each worker: exactly 40 hours per week
  - Minimum 1 worker during all coverage hours
  - Minimum 10 hours off between shifts per worker

Soft constraints (logged but don't block):
  - Full weekends off preferred (Friday + Saturday both off)
  - Consecutive days off preferred (at least 2 days off in a row)
  - Avoid splitting days off across the week
"""

import logging

logger = logging.getLogger(__name__)

MIN_SHIFT_HOURS = 6.5
MAX_SHIFT_HOURS = 12
REQUIRED_HOURS_PER_WEEK = 40
MIN_REST_HOURS = 10
STANDARD_STARTS = {0, 4, 8, 12, 16, 20}

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Coverage windows: day_index -> (start_hour, coverage_hours)
# Sunday-Thursday: 0400-0200 (22 hours)
# Friday-Saturday: 0400-0400 (24 hours)
COVERAGE = {
    0: (4, 22),   # Sunday
    1: (4, 22),   # Monday
    2: (4, 22),   # Tuesday
    3: (4, 22),   # Wednesday
    4: (4, 22),   # Thursday
    5: (4, 24),   # Friday
    6: (4, 24),   # Saturday
}


class ValidationResult:
    """Holds validation results for hard and soft constraints."""

    def __init__(self):
        self.hard_violations = []
        self.soft_violations = []
        self.soft_satisfied = []

    @property
    def is_valid(self):
        return len(self.hard_violations) == 0

    def add_hard(self, message):
        self.hard_violations.append(message)
        logger.error(f"HARD VIOLATION: {message}")

    def add_soft_violation(self, message):
        self.soft_violations.append(message)
        logger.warning(f"SOFT VIOLATION: {message}")

    def add_soft_pass(self, message):
        self.soft_satisfied.append(message)
        logger.info(f"SOFT SATISFIED: {message}")


def validate_roster(roster):
    """
    Validate the full roster against all constraints.

    Returns a ValidationResult with any violations found.
    """
    result = ValidationResult()

    for week_data in roster["weeks"]:
        wk = week_data["week_number"]
        _validate_shift_lengths(week_data, wk, result)
        _validate_start_times(week_data, wk, result)
        _validate_weekly_hours(week_data, wk, result)
        _validate_coverage(week_data, wk, result)
        _validate_rest_between_shifts(week_data, wk, result)

    # Cross-week rest validation
    _validate_cross_week_rest(roster, result)

    # Soft constraints
    _check_soft_constraints(roster, result)

    return result


def _validate_shift_lengths(week_data, wk, result):
    """Check all shift durations are within 6.5-12 hours."""
    for s in week_data["shifts"]:
        if s["duration"] < MIN_SHIFT_HOURS:
            result.add_hard(
                f"Week {wk}: {s['worker']} has {s['duration']}h shift on {s['day']} "
                f"(minimum {MIN_SHIFT_HOURS}h)"
            )
        if s["duration"] > MAX_SHIFT_HOURS:
            result.add_hard(
                f"Week {wk}: {s['worker']} has {s['duration']}h shift on {s['day']} "
                f"(maximum {MAX_SHIFT_HOURS}h)"
            )


def _validate_start_times(week_data, wk, result):
    """Check all shifts start at standard times."""
    for s in week_data["shifts"]:
        if s["start_hour"] not in STANDARD_STARTS:
            result.add_hard(
                f"Week {wk}: {s['worker']} shift on {s['day']} starts at "
                f"{s['start_time']} (not a standard start time)"
            )


def _validate_weekly_hours(week_data, wk, result):
    """Check each worker has exactly 40 hours."""
    for worker, hours in week_data["worker_hours"].items():
        if hours != REQUIRED_HOURS_PER_WEEK:
            result.add_hard(
                f"Week {wk}: {worker} has {hours}h (required {REQUIRED_HOURS_PER_WEEK}h)"
            )


def _validate_coverage(week_data, wk, result):
    """Check at least 1 worker covers every hour in the coverage window."""
    for day_idx in range(7):
        cov_start, cov_hours = COVERAGE[day_idx]
        day_shifts = [s for s in week_data["shifts"] if s["day_index"] == day_idx]

        for hour_offset in range(cov_hours):
            check_hour = cov_start + hour_offset
            covered = False
            for s in day_shifts:
                shift_start = s["start_hour"]
                shift_end = shift_start + s["duration"]
                if shift_start <= check_hour < shift_end:
                    covered = True
                    break
            if not covered:
                actual_hour = check_hour % 24
                result.add_hard(
                    f"Week {wk}: No coverage on {DAYS[day_idx]} at "
                    f"{actual_hour:02d}00 (hour {check_hour})"
                )


def _get_worker_shifts_sorted(week_data, worker_name):
    """Get shifts for a worker sorted by absolute time (day_index * 24 + start_hour)."""
    shifts = [s for s in week_data["shifts"] if s["worker"] == worker_name]
    return sorted(shifts, key=lambda s: s["day_index"] * 24 + s["start_hour"])


def _validate_rest_between_shifts(week_data, wk, result):
    """Check minimum 10 hours rest between consecutive shifts for each worker."""
    workers = roster_workers(week_data)
    for worker in workers:
        shifts = _get_worker_shifts_sorted(week_data, worker)
        for i in range(len(shifts) - 1):
            s1 = shifts[i]
            s2 = shifts[i + 1]
            end_abs = s1["day_index"] * 24 + s1["start_hour"] + s1["duration"]
            start_abs = s2["day_index"] * 24 + s2["start_hour"]
            gap = start_abs - end_abs
            if gap < MIN_REST_HOURS:
                result.add_hard(
                    f"Week {wk}: {worker} has only {gap}h rest between "
                    f"{s1['day']} {s1['start_time']}-{s1['end_time']} and "
                    f"{s2['day']} {s2['start_time']}-{s2['end_time']}"
                )


def _validate_cross_week_rest(roster, result):
    """Check rest between last shift of one week and first shift of next week."""
    weeks = roster["weeks"]
    workers = roster["workers"]

    for w_idx in range(len(weeks)):
        next_idx = (w_idx + 1) % len(weeks)
        wk = weeks[w_idx]["week_number"]
        next_wk = weeks[next_idx]["week_number"]

        for worker in workers:
            shifts_this = _get_worker_shifts_sorted(weeks[w_idx], worker)
            shifts_next = _get_worker_shifts_sorted(weeks[next_idx], worker)

            if not shifts_this or not shifts_next:
                continue

            last = shifts_this[-1]
            first = shifts_next[0]

            # Last shift ends at (day_index * 24 + start + duration) within its week
            last_end = last["day_index"] * 24 + last["start_hour"] + last["duration"]
            # First shift of next week starts at (day_index * 24 + start)
            # Total hours in a week = 7 * 24 = 168
            first_start = 168 + first["day_index"] * 24 + first["start_hour"]
            gap = first_start - last_end

            if gap < MIN_REST_HOURS:
                result.add_hard(
                    f"Cross-week Wk{wk}->Wk{next_wk}: {worker} has only {gap}h rest "
                    f"between {last['day']} {last['end_time']} and "
                    f"{first['day']} {first['start_time']}"
                )


def _check_soft_constraints(roster, result):
    """Evaluate soft constraints and log satisfaction/violations."""
    workers = roster["workers"]

    for w_idx, worker in enumerate(workers):
        weekends_off = 0
        consecutive_off_count = 0
        split_days_count = 0

        for week_data in roster["weeks"]:
            wk = week_data["week_number"]
            shifts = week_data["shifts"]
            worker_shifts = [s for s in shifts if s["worker"] == worker]
            working_days = set(s["day_index"] for s in worker_shifts)

            # Check full weekend off (Saturday=6 and Sunday=0 both off)
            sat_off = 6 not in working_days
            sun_off = 0 not in working_days
            if sat_off and sun_off:
                weekends_off += 1
                result.add_soft_pass(
                    f"Week {wk}: {worker} has full weekend off (Sat+Sun)"
                )
            elif sat_off or sun_off:
                result.add_soft_violation(
                    f"Week {wk}: {worker} has partial weekend "
                    f"({'Sat off' if sat_off else 'Sun off'} only)"
                )

            # Check consecutive days off
            off_days = sorted(set(range(7)) - working_days)
            has_consecutive = False
            for i in range(len(off_days) - 1):
                if off_days[i + 1] - off_days[i] == 1:
                    has_consecutive = True
                    break
            # Also check wrap-around (Saturday off + Sunday off)
            if 0 in off_days and 6 in off_days:
                has_consecutive = True

            if has_consecutive:
                consecutive_off_count += 1
                result.add_soft_pass(
                    f"Week {wk}: {worker} has consecutive days off "
                    f"({', '.join(DAYS[d] for d in off_days)})"
                )
            elif len(off_days) > 0:
                split_days_count += 1
                result.add_soft_violation(
                    f"Week {wk}: {worker} has split days off "
                    f"({', '.join(DAYS[d] for d in off_days)})"
                )

        # Summary per worker
        result.add_soft_pass(
            f"{worker}: {weekends_off}/4 weekends off, "
            f"{consecutive_off_count}/4 weeks with consecutive days off"
        )


def roster_workers(week_data):
    """Get unique worker names from a week's shift data."""
    return sorted(set(s["worker"] for s in week_data["shifts"]))


def get_coverage_gaps(week_data):
    """Return list of (day, hour) tuples with no coverage."""
    gaps = []
    for day_idx in range(7):
        cov_start, cov_hours = COVERAGE[day_idx]
        day_shifts = [s for s in week_data["shifts"] if s["day_index"] == day_idx]
        for hour_offset in range(cov_hours):
            check_hour = cov_start + hour_offset
            covered = any(
                s["start_hour"] <= check_hour < s["start_hour"] + s["duration"]
                for s in day_shifts
            )
            if not covered:
                gaps.append((DAYS[day_idx], f"{check_hour % 24:02d}00"))
    return gaps


def get_worker_stats(roster):
    """Compute per-worker statistics across the full cycle."""
    workers = roster["workers"]
    stats = {}

    for worker in workers:
        total_hours = 0
        weekends_off = 0
        consecutive_off_weeks = 0
        weekly_hours = []

        for week_data in roster["weeks"]:
            hours = week_data["worker_hours"][worker]
            total_hours += hours
            weekly_hours.append(hours)

            worker_shifts = [s for s in week_data["shifts"] if s["worker"] == worker]
            working_days = set(s["day_index"] for s in worker_shifts)

            if 0 not in working_days and 6 not in working_days:
                weekends_off += 1

            off_days = sorted(set(range(7)) - working_days)
            has_consecutive = False
            for i in range(len(off_days) - 1):
                if off_days[i + 1] - off_days[i] == 1:
                    has_consecutive = True
                    break
            if 0 in off_days and 6 in off_days:
                has_consecutive = True
            if has_consecutive:
                consecutive_off_weeks += 1

        stats[worker] = {
            "total_hours": total_hours,
            "weekly_hours": weekly_hours,
            "weekends_off": weekends_off,
            "consecutive_off_weeks": consecutive_off_weeks,
        }

    return stats
