"""CLI entry point for generating firework plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .planner import build_plan, parse_fireworks_file, render_station_table


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
        "--delay",
        type=float,
        default=5.0,
        help="Call-to-burst delay in seconds. Default: 5.0",
    )
    parser.add_argument(
        "--print-table",
        action="store_true",
        help="Print station assignment table to stdout.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the planner CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    fireworks = parse_fireworks_file(args.input)
    plan = build_plan(fireworks, delay_seconds=args.delay)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

    if args.print_table:
        print(render_station_table(plan.stations))

    print(f"Wrote plan JSON to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
