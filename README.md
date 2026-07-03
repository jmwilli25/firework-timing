# firework-timing

A v1 planner and live cue runner for a 3-station manual fireworks show.

## Features

- Parses fireworks input lines in `name=seconds` format.
- Balances assignments across 3 stations by total duration.
- Enforces count remainder rule:
	- `count mod 3 = 1`: station 1 gets the extra firework.
	- `count mod 3 = 2`: stations 1 and 2 get extras.
- Produces deterministic JSON plans.
- Full-screen browser execution UI:
	- countdown to next platform call,
	- rotating call order (1 -> 2 -> 3),
	- live `+/-` duration nudge adjustment,
	- prominent `DUD` button with required confirmation checkbox,
	- DUD auto-resets confirmation checkbox after activation,
	- immediate schedule reflow from current wall-clock time after DUD.

## Project Layout

- `src/firework_timing/planner.py`: parser, assignment, and schedule logic.
- `src/firework_timing/cli.py`: JSON plan generator CLI.
- `web/index.html`: execution UI shell.
- `web/app.js`: countdown engine and DUD reflow behavior.
- `tests/test_planner.py`: unit tests for planner rules.
- `fireworks.txt`: sample fireworks input.

## Requirements

- Python 3.10+

## Generate a Plan JSON

From the repository root:

```bash
PYTHONPATH=src python3 -m firework_timing \
	--input fireworks.txt \
	--output plan.json \
	--nudge 0 \
	--print-staging
```

This writes a JSON file that the web UI can load.

## Run Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

## Dry-Run Workflow (Seed 90)

Use this exact sequence for a repeatable rehearsal:

1. Generate the plan and print station staging order:

```bash
PYTHONPATH=src python3 -m firework_timing \
	--input fireworks.txt \
	--output plan.json \
	--nudge 0 \
	--seed 90 \
	--print-staging
```

2. Start the execution UI:

```bash
python3 -m http.server 8000 -d web
```

3. Open `http://localhost:8000`, load `plan.json`, then run a full rehearsal.

4. During rehearsal, test the critical live controls:

- Pause and Resume.
- Duration Nudge `+/-` adjustments.
- DUD flow (confirm checkbox then DUD button).

## Run the Live UI

Serve the `web` directory with any static file server. Example:

```bash
python3 -m http.server 8000 -d web
```

Then open:

- `http://localhost:8000`

Use **Load Plan JSON** to choose the generated `plan.json` file.

## DUD Behavior

- `DUD` is disabled until the confirmation checkbox is checked.
- On DUD click:
	- current firework is treated as spent,
	- next platform is called immediately,
	- reaction/fuse delay is applied from that exact moment,
	- all remaining cue times reflow from current wall-clock time,
	- confirmation checkbox auto-resets to unchecked.