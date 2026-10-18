"""Writes docs/benchmarks/evaluation_report.md from measured results only.

Sources:
  - Stored events from the configured data source (AISLE_DATA_SOURCE): outcomes and latency.
  - eval/results/reader.json from scripts/eval_reader.py: reading accuracy against human labels.
  - eval/results/copilot.json from scripts/eval_copilot.py: Copilot number accuracy.

A section whose source is missing says so; no number is filled in by hand.

    uv run python -m scripts.generate_benchmark_report
"""

import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from backend_service.config import get_settings
from backend_service.db.firestore_client import build_repository
from backend_service.models.interaction_event import InteractionEvent

OUT = Path("docs/benchmarks/evaluation_report.md")
READER = Path("eval/results/reader.json")
COPILOT = Path("eval/results/copilot.json")

# The targets the project set at the start (earlier report), kept so results are comparable.
TARGET_GEMINI_MS = 3_500
TARGET_TOTAL_MS = 5_000


def p95(values: List[int]) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def status(value: Optional[float], target: float) -> str:
    if value is None:
        return "Not measured"
    return "Met" if value <= target else "Not met"


def load(path: Path) -> Optional[Any]:
    return json.loads(path.read_text()) if path.exists() else None


def outcome_section(events: List[InteractionEvent]) -> List[str]:
    counts = Counter(e.conversion_outcome.value for e in events)
    picked_up = counts["taken"] + counts["returned"]
    pct = lambda n: f"{100 * n / picked_up:.1f}%" if picked_up else "n/a"  # noqa: E731
    zones = Counter(e.zone_id for e in events)
    flagged = [e for e in events if e.needs_review]
    verified = [e for e in events if e.reading_count]
    lines = [
        "## Stored clips",
        "",
        f"{len(events)} clips. Outcomes are Gemini's readings, checked against labels under 'Reading accuracy'.",
        "",
        "| Outcome | Clips | Share of picked up |",
        "|---|---|---|",
        f"| Taken | {counts['taken']} | {pct(counts['taken'])} |",
        f"| Put back | {counts['returned']} | {pct(counts['returned'])} |",
        f"| No pick-up | {counts['none']} | - |",
        "",
        "Clips per zone: " + ", ".join(f"{z} {n}" for z, n in sorted(zones.items())) + ".",
        "",
    ]
    if verified:
        lines.append(
            f"{len(verified)} clips were read {verified[0].reading_count} times each; "
            f"{len(flagged)} are flagged for a person to check."
        )
    else:
        lines.append("These clips were read once each, before verified reading existed.")
    return lines + [""]


def latency_section(events: List[InteractionEvent]) -> List[str]:
    gemini = [e.gemini_latency_ms for e in events if e.gemini_latency_ms]
    total = [e.total_latency_ms for e in events if e.total_latency_ms]
    g_mean = int(statistics.mean(gemini)) if gemini else None
    t_mean = int(statistics.mean(total)) if total else None
    fmt = lambda v: f"{v:,} ms" if v is not None else "Not measured"  # noqa: E731
    return [
        "## Latency",
        "",
        f"Measured per clip and stored with it ({len(gemini)} clips with Gemini time, {len(total)} with total time).",
        "",
        "| Metric | Mean | P95 | Target | Status |",
        "|---|---|---|---|---|",
        f"| Gemini reading | {fmt(g_mean)} | {fmt(p95(gemini) if gemini else None)} | under {TARGET_GEMINI_MS:,} ms | {status(g_mean, TARGET_GEMINI_MS)} |",
        f"| Upload to stored record | {fmt(t_mean)} | {fmt(p95(total) if total else None)} | under {TARGET_TOTAL_MS:,} ms | {status(t_mean, TARGET_TOTAL_MS)} |",
        "",
        "Edge frame rate and bandwidth savings are not reported: the camera node does not store them yet.",
        "",
    ]


def reader_section(reader: Optional[dict]) -> List[str]:
    lines = ["## Reading accuracy", ""]
    if not reader:
        return lines + ["Not measured yet. Run `scripts/eval_reader.py` after labeling clips with `eval/label.html`.", ""]
    lines.append(f"Source: `{READER}`.")
    lines.append("")
    return lines + Path(READER.with_suffix(".md")).read_text().splitlines() + [""]


def copilot_section(copilot: Optional[dict]) -> List[str]:
    lines = ["## Copilot numbers", ""]
    if not copilot:
        return lines + ["Not measured yet. Run `scripts/eval_copilot.py`.", ""]
    lines.append(f"Source: `{COPILOT}`.")
    lines.append("")
    return lines + Path(COPILOT.with_suffix(".md")).read_text().splitlines() + [""]


def main() -> None:
    settings = get_settings()
    events = build_repository(settings).list_events(limit=500)
    lines = [
        "# AIsle benchmark report",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/generate_benchmark_report.py` "
        f"from the `{settings.AISLE_DATA_SOURCE}` data source and `{settings.GEMINI_MODEL}`. "
        "Every number below comes from stored events or an evaluation result file.",
        "",
    ]
    lines += reader_section(load(READER))
    lines += copilot_section(load(COPILOT))
    lines += outcome_section(events)
    lines += latency_section(events)
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
