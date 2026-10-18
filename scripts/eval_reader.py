"""Measures how well each clip reader matches human labels.

Readers, all given the same local clips:
  baseline  The original analyzer: one free-form JSON prompt, no schema, no behavior tags.
  single    One structured read with the current schema (picked_up_item, left_with_item, tags).
  verified  READS_PER_CLIP structured reads, majority vote and consistency check.

Usage (needs Gemini credentials; calls Gemini about clips x repeats x (2 + READS_PER_CLIP) times):
    uv run python -m scripts.eval_reader --labels eval/labels.json --repeats 3

Writes eval/results/reader.json and eval/results/reader.md.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from backend_service.config import get_settings
from backend_service.errors import GeminiError
from backend_service.models.interaction_event import ClipAnalysis
from backend_service.services.clip_verification import combine, consistency_issues
from backend_service.services.gemini_analyzer import SYSTEM_PROMPT, GeminiAnalyzerService
from backend_service.services.gemini_client import GeminiClient
from backend_service.services.storage_service import StorageService

CLIP_DIR = Path("temp_uploads/clip_cache")
RESULTS_DIR = Path("eval/results")

# Vertex AI list prices, USD per million tokens (video counts as input). Models not listed
# are costed at gemini-2.5-flash prices, and the report says so.
PRICES = {"gemini-2.5-flash": (0.30, 2.50)}
PRICE_FALLBACK = "gemini-2.5-flash"

# The analyzer prompt as first committed (8cbe15e), before schemas and tags.
BASELINE_PROMPT = """You are an expert AI retail behavioral analyst for in-store physical retail analytics.
You analyze short overhead or shelf-facing video clips of customer interactions with retail store shelves and displays.

Analyze the video and output a strict JSON object with EXACTLY the following fields:
{
  "zone_dwell_time_seconds": <integer: total seconds customer dwelled in the zone>,
  "interaction_type": "<one of: 'passed_by', 'browsed', 'examined', 'compared'>",
  "conversion_outcome": "<one of: 'taken', 'returned', 'none'>",
  "product_category_engaged": "<string: descriptive shelf section or product description>",
  "shopper_group_size": <integer: 1, 2, or more>,
  "estimated_demographic": "<one of: 'young_adult', 'adult', 'senior', 'unknown'>",
  "behavioral_summary": "<string: 1-2 sentence narrative detailing customer movement, hesitation, physical touches, and final action>"
}

Definitions:
- conversion_outcome:
  - 'taken': Placed in cart, basket, or held to purchase.
  - 'returned': Placed back onto the shelf (cart abandonment).
  - 'none': No product was physically removed.

Return ONLY the valid JSON object without markdown code blocks or additional commentary.
"""


# Who produced the labels decides what the accuracy row may be called.
LABEL_SOURCES = {
    "human": "human labels",
    "claude-frames": "an independent frame-by-frame review by Claude (not human labels)",
}


class Result(dict):
    """One reader's answer for one clip in one repeat."""


def video_part(clip: Path) -> Any:
    from google.genai import types

    return types.Part.from_bytes(data=clip.read_bytes(), mime_type="video/mp4")


def baseline_reader(gemini: GeminiClient) -> Callable[[Path, str], Result]:
    from google.genai import types

    def run(clip: Path, zone_id: str) -> Result:
        response = gemini._client.models.generate_content(  # noqa: SLF001 - eval reaches past the wrapper on purpose
            model=gemini.model,
            contents=[video_part(clip), f"Zone ID: {zone_id}\nAnalyze the shopper behavior in this clip and return the JSON metric object."],
            config=types.GenerateContentConfig(
                system_instruction=BASELINE_PROMPT, temperature=0.2, response_mime_type="application/json"
            ),
        )
        gemini._count(response)  # noqa: SLF001
        data = json.loads(response.text or "{}")
        return Result(outcome=str(data.get("conversion_outcome", "")).lower(), tags=[], flagged=False, calls=1)

    return run


def single_reader(gemini: GeminiClient) -> Callable[[Path, str], Result]:
    def run(clip: Path, zone_id: str) -> Result:
        read = gemini.generate(
            system=SYSTEM_PROMPT,
            contents=[video_part(clip), f"Zone ID: {zone_id}\nAnalyze the shopper behavior in this clip."],
            schema=ClipAnalysis,
            temperature=0.2,
        )
        return Result(
            outcome=read.conversion_outcome.value,
            tags=[t.value for t in read.behavior_tags],
            flagged=False,
            contradiction=bool(consistency_issues(read)),
            calls=1,
        )

    return run


def verified_reader(analyzer: GeminiAnalyzerService) -> Callable[[Path, str], Result]:
    def run(clip: Path, zone_id: str) -> Result:
        reads = analyzer.read_clip(str(clip), zone_id)
        consensus = combine(reads)
        return Result(
            outcome=consensus.analysis.conversion_outcome.value,
            tags=[t.value for t in consensus.analysis.behavior_tags],
            flagged=consensus.needs_review,
            contradiction=bool(consistency_issues(consensus.analysis)),
            calls=len(reads),
        )

    return run


def tag_counts(predicted: Set[str], truth: Set[str]) -> Counter:
    return Counter(tp=len(predicted & truth), fp=len(predicted - truth), fn=len(truth - predicted))


def score(runs: Dict[str, List[Result]], labels: Dict[str, dict]) -> Dict[str, Any]:
    """Scores one reader over every clip and repeat."""
    clear = [cid for cid, label in labels.items() if label["outcome"] != "unclear"]
    correct, total, tags, latencies, calls = 0, 0, Counter(), [], 0
    stable = contradictions = reads = 0
    flagged_wrong = flagged_right = unflagged_wrong = 0
    unclear_reads = unclear_flagged = 0
    for cid, results in runs.items():
        outcomes = [r["outcome"] for r in results]
        stable += len(set(outcomes)) == 1
        for r in results:
            latencies.append(r["latency_ms"])
            calls += r["calls"]
            reads += 1
            contradictions += bool(r.get("contradiction"))
            if cid not in clear:
                unclear_reads += 1
                unclear_flagged += bool(r["flagged"])
                continue
            right = r["outcome"] == labels[cid]["outcome"]
            correct += right
            total += 1
            tags += tag_counts(set(r["tags"]), set(labels[cid]["behavior_tags"]))
            if r["flagged"]:
                flagged_right += right
                flagged_wrong += not right
            else:
                unflagged_wrong += not right
    precision = tags["tp"] / (tags["tp"] + tags["fp"]) if tags["tp"] + tags["fp"] else 0.0
    recall = tags["tp"] / (tags["tp"] + tags["fn"]) if tags["tp"] + tags["fn"] else 0.0
    flagged = flagged_right + flagged_wrong
    return {
        "outcome_accuracy": round(correct / total, 3) if total else None,
        "scored_reads": total,
        "tag_f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "stable_clips": f"{stable} of {len(runs)}",
        "stability": round(stable / len(runs), 3) if runs else None,
        "flag_precision": round(flagged_wrong / flagged, 3) if flagged else None,
        "wrong_reads_flagged": f"{flagged_wrong} of {flagged_wrong + unflagged_wrong}",
        "unclear_reads_flagged": f"{unclear_flagged} of {unclear_reads}",
        "self_contradictions": f"{contradictions} of {reads}",
        "mean_latency_ms": int(statistics.mean(latencies)) if latencies else None,
        "calls_per_clip": round(calls / len(latencies), 2) if latencies else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", default="eval/labels.json")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--readers", default="baseline,single,verified")
    parser.add_argument("--only", nargs="*", help="Limit to these event IDs")
    args = parser.parse_args()

    if not Path(args.labels).exists():
        print(f"No labels at {args.labels}. Label the clips with eval/label.html first.", file=sys.stderr)
        return 1
    labels_file = json.loads(Path(args.labels).read_text())
    label_source = labels_file.get("labeled_by")
    if label_source not in LABEL_SOURCES:
        print(f"Unknown label source {label_source!r}; expected one of {sorted(LABEL_SOURCES)}.", file=sys.stderr)
        return 1
    labels: Dict[str, dict] = labels_file["clips"]
    seed = {e["event_id"]: e for e in json.loads(Path("backend_service/data/seed_benchmark_events.json").read_text())}
    clip_ids = [cid for cid in sorted(labels) if not args.only or cid in args.only]
    missing = [cid for cid in clip_ids if not (CLIP_DIR / f"{cid}.mp4").exists()]
    if missing:
        print(f"Missing local clips (open them once in the dashboard to cache): {missing}", file=sys.stderr)
        return 1

    settings = get_settings()
    gemini = GeminiClient(settings)
    if not gemini.available:
        print("Gemini is not configured.", file=sys.stderr)
        return 1
    analyzer = GeminiAnalyzerService(gemini, StorageService(settings, use_gcs=False), settings.READS_PER_CLIP)
    readers = {"baseline": baseline_reader(gemini), "single": single_reader(gemini), "verified": verified_reader(analyzer)}
    chosen = [name for name in args.readers.split(",") if name in readers]

    report: Dict[str, Any] = {
        "model": gemini.model,
        "repeats": args.repeats,
        "clips": len(clip_ids),
        "label_source": LABEL_SOURCES[label_source],
        "cost_basis": gemini.model if gemini.model in PRICES else f"{PRICE_FALLBACK} list prices ({gemini.model} not listed)",
        "readers": {},
    }
    per_clip: Dict[str, Dict[str, List[str]]] = {cid: {} for cid in clip_ids}
    for name in chosen:
        usage_before = dict(gemini.usage)
        runs: Dict[str, List[Result]] = {}
        for cid in clip_ids:
            zone = seed.get(cid, {}).get("zone_id", "unknown")
            runs[cid] = []
            for _ in range(args.repeats):
                start = time.time()
                try:
                    result = readers[name](CLIP_DIR / f"{cid}.mp4", zone)
                except (GeminiError, json.JSONDecodeError) as e:
                    result = Result(outcome="error", tags=[], flagged=False, calls=1, error=str(e))
                result["latency_ms"] = int((time.time() - start) * 1000)
                runs[cid].append(result)
            per_clip[cid][name] = [r["outcome"] for r in runs[cid]]
            print(f"{name:9} {cid} truth={labels[cid]['outcome']:9} got={per_clip[cid][name]}", flush=True)
        used = {k: gemini.usage[k] - usage_before[k] for k in gemini.usage}
        price_in, price_out = PRICES.get(gemini.model, PRICES[PRICE_FALLBACK])
        cost = used["input_tokens"] / 1e6 * price_in + used["output_tokens"] / 1e6 * price_out
        reads = len(clip_ids) * args.repeats
        report["readers"][name] = {**score(runs, labels), "usd_per_clip": round(cost / reads, 5), "tokens": used}

    unclear = [cid for cid in clip_ids if labels[cid]["outcome"] == "unclear"]
    duplicates = {cid: labels[cid]["same_shopper_as"] for cid in clip_ids if labels[cid].get("same_shopper_as")}
    report.update(
        unclear_clips=unclear,
        same_shopper_pairs=duplicates,
        truth_counts=dict(Counter(labels[cid]["outcome"] for cid in clip_ids)),
        per_clip={cid: {"truth": labels[cid]["outcome"], **per_clip[cid]} for cid in clip_ids},
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "reader.json").write_text(json.dumps(report, indent=2) + "\n")
    (RESULTS_DIR / "reader.md").write_text(markdown(report))
    print(markdown(report))
    return 0


def markdown(report: Dict[str, Any]) -> str:
    rows = [
        ("Outcome agreement with labels", "outcome_accuracy"),
        ("Behavior tag F1", "tag_f1"),
        ("Same outcome on every repeat", "stable_clips"),
        ("Wrong reads that were flagged", "wrong_reads_flagged"),
        ("Flagged reads that were wrong", "flag_precision"),
        ("Unclear clips that were flagged", "unclear_reads_flagged"),
        ("Outcome contradicts own observations", "self_contradictions"),
        ("Gemini calls per clip", "calls_per_clip"),
        ("Mean latency (ms)", "mean_latency_ms"),
        (f"Cost per clip (USD, {report['cost_basis']})", "usd_per_clip"),
    ]
    names = list(report["readers"])
    lines = [
        f"Model {report['model']}, {report['clips']} clips, {report['repeats']} repeats per reader. "
        f"Labels: {report['label_source']}. Agreement counts only clips whose outcome the review could tell "
        f"({len(report['unclear_clips'])} of {report['clips']} could not be told from the clip).",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for label, key in rows:
        lines.append(f"| {label} | " + " | ".join(str(report["readers"][n].get(key, "")) for n in names) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
