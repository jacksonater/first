"""
generate_roster.py - Entry point for the 4-week rotating roster generator.

Usage:
    python generate_roster.py

Outputs:
    roster.html  - Colour-coded weekly grid (open in a browser)
    roster.json  - Machine-readable schedule data
    Terminal     - Summary table with hours, coverage and constraint checks
"""

import json
import logging
import sys

from scheduler import generate_roster, roster_to_json
from validator import validate_roster
from renderer import render_html, print_terminal_summary

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def main():
    # Generate the 4-week roster
    roster = generate_roster()

    # Validate all hard and soft constraints
    validation = validate_roster(roster)

    # Terminal output
    print_terminal_summary(roster, validation)

    # HTML output
    html_path = render_html(roster, validation, "roster.html")
    print(f"\nHTML roster written to: {html_path}")

    # JSON output
    json_path = "roster.json"
    with open(json_path, "w") as f:
        f.write(roster_to_json(roster))
    print(f"JSON roster written to: {json_path}")

    if not validation.is_valid:
        print(
            f"\nERROR: {len(validation.hard_violations)} hard constraint violation(s) found.",
            file=sys.stderr,
        )
        return 1

    print("\nAll hard constraints satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
