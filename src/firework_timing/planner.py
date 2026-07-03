"""Core planning and scheduling logic for the firework timing app."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import random
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class Firework:
    """Represents one firework item from the input list."""

    firework_id: str
    name: str
    duration_seconds: float
    source_line: int


@dataclass(frozen=True)
class CueEvent:
    """Represents one call cue in the execution timeline."""

    order_index: int
    station_id: int
    firework_id: str
    firework_name: str
    duration_seconds: float


@dataclass(frozen=True)
class StationPlan:
    """Represents one station's assigned fireworks."""

    station_id: int
    fireworks: List[Firework]
    total_seconds: float


@dataclass(frozen=True)
class Plan:
    """Represents the full generated plan used by the planner and UI."""

    stations: List[StationPlan]
    events: List[CueEvent]

    def to_dict(self) -> Dict[str, object]:
        """Serialize the plan to a JSON-friendly dictionary."""
        return {
            "version": 1,
            "stations": [
                {
                    "station_id": station.station_id,
                    "total_seconds": station.total_seconds,
                    "fireworks": [asdict(firework) for firework in station.fireworks],
                }
                for station in self.stations
            ],
            "events": [asdict(event) for event in self.events],
        }


def parse_fireworks_text(raw_text: str) -> List[Firework]:
    """Parse firework lines in ``name=seconds`` format.

    Blank lines are allowed and ignored. Duplicate names are allowed because
    users may buy multiple identical products.
    """
    fireworks: List[Firework] = []
    seen_counts: Dict[str, int] = {}
    base_duration_by_name: Dict[str, Tuple[float, int]] = {}

    def normalize_base_name(firework_name: str) -> str | None:
        """Return base product name for numbered variants like willow-1."""
        left, sep, right = firework_name.rpartition("-")
        if sep and right.isdigit() and left:
            return left
        return None

    for index, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        if "=" not in line:
            raise ValueError(
                f"Invalid line {index}: expected 'name=seconds', got '{line}'."
            )

        name_part, duration_part = line.split("=", 1)
        name = name_part.strip()
        duration_text = duration_part.strip()

        if not name:
            raise ValueError(f"Invalid line {index}: firework name cannot be blank.")

        try:
            duration_seconds = float(duration_text)
        except ValueError as error:
            raise ValueError(
                f"Invalid line {index}: duration must be numeric, got '{duration_text}'."
            ) from error

        if duration_seconds <= 0:
            raise ValueError(
                f"Invalid line {index}: duration must be > 0, got {duration_seconds}."
            )

        base_name = normalize_base_name(name)
        if base_name is not None:
            prior_entry = base_duration_by_name.get(base_name)
            if prior_entry is None:
                base_duration_by_name[base_name] = (duration_seconds, index)
            else:
                prior_duration, prior_line = prior_entry
                if prior_duration != duration_seconds:
                    raise ValueError(
                        "Invalid line "
                        f"{index}: '{name}' duration {duration_seconds:g}s does not "
                        "match other "
                        f"'{base_name}-*' entries set to {prior_duration:g}s on "
                        f"line {prior_line}."
                    )

        occurrence = seen_counts.get(name, 0) + 1
        seen_counts[name] = occurrence
        firework_id = f"{name}#{occurrence}"

        fireworks.append(
            Firework(
                firework_id=firework_id,
                name=name,
                duration_seconds=duration_seconds,
                source_line=index,
            )
        )

    if not fireworks:
        raise ValueError("No fireworks found. Add lines in 'name=seconds' format.")

    return fireworks


def parse_fireworks_file(file_path: Path) -> List[Firework]:
    """Load and parse fireworks from a text file path."""
    return parse_fireworks_text(file_path.read_text(encoding="utf-8"))


def _station_target_counts(total_fireworks: int, station_count: int) -> List[int]:
    """Compute per-station firework counts following remainder placement rules."""
    if station_count <= 0:
        raise ValueError("station_count must be positive.")

    base = total_fireworks // station_count
    remainder = total_fireworks % station_count

    targets = [base] * station_count
    for station_index in range(remainder):
        targets[station_index] += 1

    return targets


def assign_fireworks(
    fireworks: Sequence[Firework],
    station_count: int = 3,
    rng: random.Random | None = None,
) -> List[StationPlan]:
    """Assign fireworks to stations with balanced duration and fixed count rules."""
    if station_count != 3:
        raise ValueError("This planner currently supports exactly 3 stations.")

    targets = _station_target_counts(len(fireworks), station_count)
    station_items: List[List[Firework]] = [[] for _ in range(station_count)]
    station_totals = [0.0] * station_count

    # Sort by longest duration first so the greedy balancing is stable.
    sorted_fireworks = sorted(
        fireworks,
        key=lambda item: (-item.duration_seconds, item.name, item.source_line),
    )

    for firework in sorted_fireworks:
        candidate_indices = [
            idx for idx in range(station_count) if len(station_items[idx]) < targets[idx]
        ]
        best_score = min(
            (station_totals[idx], len(station_items[idx])) for idx in candidate_indices
        )
        best_candidates = [
            idx
            for idx in candidate_indices
            if (station_totals[idx], len(station_items[idx])) == best_score
        ]

        if rng is None:
            best_idx = min(best_candidates)
        else:
            best_idx = rng.choice(best_candidates)

        station_items[best_idx].append(firework)
        station_totals[best_idx] += firework.duration_seconds

    station_plans = [
        StationPlan(
            station_id=idx + 1,
            fireworks=station_items[idx],
            total_seconds=station_totals[idx],
        )
        for idx in range(station_count)
    ]

    return station_plans


def _product_name(firework_name: str) -> str:
    """Normalize numbered variants to product name for repeat avoidance."""
    left, sep, right = firework_name.rpartition("-")
    if sep and right.isdigit() and left:
        return left
    return firework_name


def _zigzag_durations(fireworks: List[Firework]) -> List[Firework]:
    """Reorder fireworks so durations alternate short-long-short-long.

    Sorting monotonically (all long first or all short first) would make the
    show trend in one direction. Zigzagging gives a varied feel across rounds
    by interleaving the shortest and longest remaining items.
    """
    ascending = sorted(fireworks, key=lambda item: item.duration_seconds)
    result: List[Firework] = []
    left, right = 0, len(ascending) - 1
    take_short = True
    while left <= right:
        if take_short:
            result.append(ascending[left])
            left += 1
        else:
            result.append(ascending[right])
            right -= 1
        take_short = not take_short
    return result


def _choose_station_firework(
    queue: List[Firework], last_product_name: str | None, rng: random.Random
) -> Firework:
    """Choose next firework for a station while avoiding immediate repeats."""
    non_repeat = [
        firework for firework in queue if _product_name(firework.name) != last_product_name
    ]
    pool = non_repeat if non_repeat else queue
    return rng.choice(pool)


def _count_adjacent_product_collisions(sequence: Sequence[Tuple[int, Firework]]) -> int:
    """Count back-to-back events that use the same normalized product name."""
    collisions = 0
    previous_name: str | None = None
    for _, firework in sequence:
        current_name = _product_name(firework.name)
        if previous_name == current_name:
            collisions += 1
        previous_name = current_name
    return collisions


def _build_event_sequence_once(
    stations: Sequence[StationPlan], rng: random.Random
) -> List[Tuple[int, Firework]]:
    """Build one candidate sequence using anti-repeat random selection."""
    station_queues: Dict[int, List[Firework]] = {
        station.station_id: _zigzag_durations(list(station.fireworks))
        for station in stations
    }

    sequence: List[Tuple[int, Firework]] = []
    last_product_name: str | None = None

    while any(station_queues.values()):
        for station_id in (1, 2, 3):
            queue = station_queues[station_id]
            if not queue:
                continue

            selected = _choose_station_firework(queue, last_product_name, rng)
            queue.remove(selected)
            sequence.append((station_id, selected))
            last_product_name = _product_name(selected.name)

    return sequence


def _build_event_sequence(
    stations: Sequence[StationPlan], rng: random.Random
) -> List[Tuple[int, Firework]]:
    """Create station call order in rotating station sequence 1, 2, 3.

    The planner samples multiple valid randomized sequences and picks the one
    with the fewest adjacent same-product collisions.
    """
    best_sequence: List[Tuple[int, Firework]] = []
    best_collisions: int | None = None

    search_attempts = max(24, len(stations) * 40)
    for _ in range(search_attempts):
        attempt_rng = random.Random(rng.randrange(0, 2**32))
        candidate = _build_event_sequence_once(stations, attempt_rng)
        candidate_collisions = _count_adjacent_product_collisions(candidate)

        if best_collisions is None or candidate_collisions < best_collisions:
            best_collisions = candidate_collisions
            best_sequence = candidate
            if best_collisions == 0:
                break

    return best_sequence


def build_schedule(
    stations: Sequence[StationPlan], rng: random.Random
) -> List[CueEvent]:
    """Build the execution timeline with overlap-preferred cue timing."""
    sequence = _build_event_sequence(stations, rng)
    events: List[CueEvent] = []

    for order_index, (station_id, firework) in enumerate(sequence):
        events.append(
            CueEvent(
                order_index=order_index,
                station_id=station_id,
                firework_id=firework.firework_id,
                firework_name=firework.name,
                duration_seconds=firework.duration_seconds,
            )
        )

    return events


def build_plan(
    fireworks: Sequence[Firework],
    random_seed: int | None = None,
) -> Plan:
    """Build the complete station assignment and execution schedule.

    When ``random_seed`` is omitted, the planner uses true randomness to reduce
    repeated back-to-back product names in the cue sequence.
    """
    rng = random.Random(random_seed)
    stations = assign_fireworks(fireworks, rng=rng)
    events = build_schedule(stations, rng=rng)
    return Plan(stations=stations, events=events)


def render_station_table(stations: Iterable[StationPlan]) -> str:
    """Render a plain-text table for quick terminal review."""
    lines = [
        "Station | Total Seconds | Fireworks",
        "------- | ------------- | ---------",
    ]
    for station in stations:
        firework_names = ", ".join(
            f"{firework.name} ({firework.duration_seconds:g}s)"
            for firework in station.fireworks
        )
        lines.append(
            f"{station.station_id} | {station.total_seconds:g} | {firework_names}"
        )
    return "\n".join(lines)
