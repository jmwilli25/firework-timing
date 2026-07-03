"""CLI entry point for generating firework plans."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from .planner import build_plan, parse_fireworks_file


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="firework-timing",
        description="Generate station assignments and execution schedule JSON.",
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to input file in name=seconds format.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where JSON plan will be written.",
    )
    parser.add_argument(
        "--nudge",
        type=float,
        default=0.0,
        help="Call duration nudge in seconds. Default: 0.0",
    )
    parser.add_argument(
        "--print-staging",
        action="store_true",
        help="Print per-station firing order from generated events.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible plan generation.",
    )

    return parser


def _print_staging(plan_dict: dict) -> None:
    """Print per-station staging order from serialized plan events."""
    per_station = defaultdict(list)
    for event in sorted(plan_dict["events"], key=lambda item: item["order_index"]):
        per_station[event["station_id"]].append(event)

    for station_id in sorted(per_station):
        print(f"Station {station_id} staging order:")
        for index, event in enumerate(per_station[station_id], start=1):
            print(
                f"  {index:02d}. {event['firework_name']} "
                f"({event['duration_seconds']}s)"
            )
        print()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the planner CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    fireworks = parse_fireworks_file(args.input)
    plan = build_plan(
        fireworks,
        nudge_seconds=args.nudge,
        random_seed=args.seed,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized_plan = plan.to_dict()
    args.output.write_text(json.dumps(serialized_plan, indent=2), encoding="utf-8")

    if args.print_staging:
        _print_staging(serialized_plan)

    print(f"Wrote plan JSON to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
