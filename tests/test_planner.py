"""Unit tests for planner and scheduling behavior."""

from __future__ import annotations

import random
import unittest

from firework_timing.planner import (
    _station_target_counts,
    assign_fireworks,
    build_schedule,
    build_plan,
    parse_fireworks_text,
)


class PlannerTests(unittest.TestCase):
    """Tests core planner rules from prompt requirements."""

    def test_parse_rejects_bad_lines(self) -> None:
        """Parser should fail on malformed input."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 1: expected 'name=seconds', got 'bad-line-without-equals'\.",
        ):
            parse_fireworks_text("bad-line-without-equals")

    def test_parse_rejects_blank_name(self) -> None:
        """Parser should fail when name side is empty."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 1: firework name cannot be blank\.",
        ):
            parse_fireworks_text("=30")

    def test_parse_rejects_non_numeric_duration(self) -> None:
        """Parser should fail on non-numeric durations."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 1: duration must be numeric, got '30seconds'\.",
        ):
            parse_fireworks_text("fw-1=30seconds")

    def test_parse_rejects_zero_duration(self) -> None:
        """Parser should fail for zero-second fireworks."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 1: duration must be > 0, got 0\.0\.",
        ):
            parse_fireworks_text("fw-1=0")

    def test_parse_rejects_negative_duration(self) -> None:
        """Parser should fail for negative durations."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 1: duration must be > 0, got -3\.0\.",
        ):
            parse_fireworks_text("fw-1=-3")

    def test_parse_rejects_empty_input(self) -> None:
        """Parser should fail when no valid fireworks are provided."""
        with self.assertRaisesRegex(
            ValueError,
            r"No fireworks found\. Add lines in 'name=seconds' format\.",
        ):
            parse_fireworks_text("\n\n")

    def test_parse_accepts_duplicates_and_counts_ids(self) -> None:
        """Duplicate names should produce unique ids."""
        fireworks = parse_fireworks_text("fw=10\nfw=12\n")
        self.assertEqual("fw#1", fireworks[0].firework_id)
        self.assertEqual("fw#2", fireworks[1].firework_id)

    def test_numbered_variants_must_match_duration(self) -> None:
        """Variant names like willow-1 and willow-2 should share duration."""
        with self.assertRaisesRegex(
            ValueError,
            r"Invalid line 2: 'willow-2' duration 47s does not match other "
            r"'willow-\*' entries set to 50s on line 1\.",
        ):
            parse_fireworks_text("willow-1=50\nwillow-2=47\n")

    def test_numbered_variants_with_same_duration_are_valid(self) -> None:
        """Matching variant durations should parse successfully."""
        fireworks = parse_fireworks_text("willow-1=50\nwillow-2=50\n")
        self.assertEqual(2, len(fireworks))

    def test_remainder_rule_mod_1(self) -> None:
        """When count mod 3 = 1, station 1 gets extra firework."""
        fireworks = parse_fireworks_text(
            "\n".join(
                [
                    "a=30",
                    "b=29",
                    "c=28",
                    "d=27",
                    "e=26",
                    "f=25",
                    "g=24",
                ]
            )
        )
        stations = assign_fireworks(fireworks)
        counts = [len(station.fireworks) for station in stations]
        self.assertEqual([3, 2, 2], counts)

    def test_remainder_rule_mod_2(self) -> None:
        """When count mod 3 = 2, stations 1 and 2 get extras."""
        fireworks = parse_fireworks_text(
            "\n".join(
                [
                    "a=30",
                    "b=29",
                    "c=28",
                    "d=27",
                    "e=26",
                    "f=25",
                    "g=24",
                    "h=23",
                ]
            )
        )
        stations = assign_fireworks(fireworks)
        counts = [len(station.fireworks) for station in stations]
        self.assertEqual([3, 3, 2], counts)

    def test_plan_generation_is_deterministic(self) -> None:
        """Same input and same seed should produce the same event sequence."""
        raw = "\n".join(
            [
                "w1=40",
                "w2=35",
                "w3=30",
                "w4=25",
                "w5=20",
                "w6=15",
            ]
        )
        fireworks = parse_fireworks_text(raw)
        plan_one = build_plan(fireworks, random_seed=2026)
        plan_two = build_plan(fireworks, random_seed=2026)

        one_keys = [
            (event.station_id, event.firework_id)
            for event in plan_one.events
        ]
        two_keys = [
            (event.station_id, event.firework_id)
            for event in plan_two.events
        ]
        self.assertEqual(one_keys, two_keys)

    def test_schedule_uses_rotation_order(self) -> None:
        """Events should rotate stations 1 -> 2 -> 3."""
        fireworks = parse_fireworks_text(
            "\n".join(
                [
                    "a=30",
                    "b=30",
                    "c=30",
                    "d=30",
                    "e=30",
                    "f=30",
                ]
            )
        )
        plan = build_plan(fireworks)
        stations = [event.station_id for event in plan.events]
        self.assertEqual([1, 2, 3, 1, 2, 3], stations)

    def test_station_target_counts_rejects_non_positive_count(self) -> None:
        """Target count helper should reject invalid station_count values."""
        with self.assertRaises(ValueError):
            _station_target_counts(total_fireworks=10, station_count=0)

    def test_assign_fireworks_rejects_non_three_station_config(self) -> None:
        """Assignment should reject non-3-station configurations."""
        fireworks = parse_fireworks_text("a=10\nb=10\nc=10")
        with self.assertRaises(ValueError):
            assign_fireworks(fireworks, station_count=2)

    def test_scheduler_avoids_immediate_repeat_when_possible(self) -> None:
        """Scheduler should avoid same product in back-to-back cues when possible."""
        fireworks = parse_fireworks_text(
            "\n".join(
                [
                    "fw-1=30",
                    "fw-2=30",
                    "fw-3=30",
                    "fw1-1=45",
                    "fw1-2=45",
                    "fw1-3=45",
                ]
            )
        )
        plan = build_plan(fireworks, random_seed=99)
        product_names = [event.firework_name.split("-")[0] for event in plan.events]
        for current, following in zip(product_names, product_names[1:]):
            self.assertNotEqual(current, following)

    def test_three_and_three_pairing_avoids_adjacent_repeats(self) -> None:
        """Classic 3+3 case should not place same product in consecutive events."""
        fireworks = parse_fireworks_text(
            "\n".join(
                [
                    "fw-1=30",
                    "fw-2=30",
                    "fw-3=30",
                    "fw1-1=45",
                    "fw1-2=45",
                    "fw1-3=45",
                ]
            )
        )
        plan = build_plan(fireworks, random_seed=90)
        product_names = [event.firework_name.split("-")[0] for event in plan.events]
        for current, following in zip(product_names, product_names[1:]):
            self.assertNotEqual(current, following)


if __name__ == "__main__":
    unittest.main()
