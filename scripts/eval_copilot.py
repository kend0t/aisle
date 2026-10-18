"""Checks Copilot's numbers against the counts the dashboard shows.

Two designs answer the same questions:
  context  The earlier Copilot: every stored event in the prompt, Gemini does the arithmetic.
  tools    The current Copilot: Gemini calls counting tools and quotes their results.

Expected numbers are computed by the same counting functions the dashboard's figures
match, so a question passes when every expected number appears in the answer and every
cited clip exists.

Usage (needs Gemini credentials; about 2 x questions x repeats Gemini requests):
    AISLE_DATA_SOURCE=seed uv run python -m scripts.eval_copilot --repeats 2

Writes eval/results/copilot.json and eval/results/copilot.md.
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from backend_service.config import get_settings
from backend_service.db.firestore_client import build_repository
from backend_service.errors import GeminiError
from backend_service.models.chat import ChatRequest
from backend_service.services.chat_service import EVENT_ID_PATTERN, StoreChatService
from backend_service.services.gemini_client import GeminiClient

QUESTIONS = Path("eval/copilot_questions.json")
RESULTS_DIR = Path("eval/results")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split()
)}


def number_present(expected: float, answer: str) -> bool:
    """True when the answer states the number, in digits or words, allowing whole-percent rounding (35.7 -> 36)."""
    found = {float(n) for n in NUMBER.findall(answer.replace(",", ""))}
    found |= {float(WORDS[w]) for w in re.findall(r"[a-z]+", answer.lower()) if w in WORDS}
    return any(abs(f - expected) < 0.05 or (expected != int(expected) and f == round(expected)) for f in found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--rescore", action="store_true", help="Score the saved answers again; no Gemini calls")
    args = parser.parse_args()
    if args.rescore:
        return rescore()

    settings = get_settings()
    gemini = GeminiClient(settings)
    if not gemini.available:
        print("Gemini is not configured.", file=sys.stderr)
        return 1
    repo = build_repository(settings)
    chat = StoreChatService(repo, gemini)
    known_ids = {e.event_id for e in repo.list_events(limit=500)}
    tools = chat.tools.as_functions()

    questions = json.loads(QUESTIONS.read_text())
    designs = {
        "context": lambda q: (chat.answer_with_context(ChatRequest(message=q)), []),
        "tools": lambda q: chat.answer_with_tools(ChatRequest(message=q)),
    }
    report: Dict[str, Any] = {"model": gemini.model, "questions": len(questions), "repeats": args.repeats, "designs": {}}

    for name, answer in designs.items():
        passed, latencies, details = 0, [], []
        for q in questions:
            expected = [tools[e["tool"]](**e["args"])[e["key"]] for e in q["expect"]]
            for _ in range(args.repeats):
                start = time.time()
                try:
                    reply, trace = answer(q["question"])
                    text = reply.response
                except GeminiError as e:
                    text, trace = f"error: {e}", []
                latencies.append(int((time.time() - start) * 1000))
                numbers_ok = all(number_present(float(x), text) for x in expected if x is not None)
                citations_ok = all(cid in known_ids for cid in EVENT_ID_PATTERN.findall(text))
                ok = numbers_ok and citations_ok
                passed += ok
                details.append(
                    {"question": q["question"], "expected": expected, "passed": ok, "answer": text, "tool_calls": trace}
                )
                print(f"{name:7} {'PASS' if ok else 'FAIL'} {q['question']} expected={expected}", flush=True)
        total = len(questions) * args.repeats
        report["designs"][name] = {
            "pass_rate": round(passed / total, 3),
            "passed": f"{passed} of {total}",
            "mean_latency_ms": int(statistics.mean(latencies)),
            "answers": details,
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "copilot.json").write_text(json.dumps(report, indent=2) + "\n")
    table = markdown(report)
    (RESULTS_DIR / "copilot.md").write_text(table)
    print(table)
    return 0


def rescore() -> int:
    report = json.loads((RESULTS_DIR / "copilot.json").read_text())
    known_ids = {e.event_id for e in build_repository(get_settings()).list_events(limit=500)}
    for design in report["designs"].values():
        for a in design["answers"]:
            a["passed"] = (
                "error:" not in a["answer"]
                and all(number_present(float(x), a["answer"]) for x in a["expected"] if x is not None)
                and all(cid in known_ids for cid in EVENT_ID_PATTERN.findall(a["answer"]))
            )
        passed = sum(a["passed"] for a in design["answers"])
        design.update(passed=f"{passed} of {len(design['answers'])}", pass_rate=round(passed / len(design["answers"]), 3))
    (RESULTS_DIR / "copilot.json").write_text(json.dumps(report, indent=2) + "\n")
    (RESULTS_DIR / "copilot.md").write_text(markdown(report))
    print(markdown(report))
    return 0


def markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"Model {report['model']}, {report['questions']} questions, {report['repeats']} repeats per design.",
        "",
        "| Design | Answers with every number right | Mean latency (ms) |",
        "|---|---|---|",
    ]
    for name, d in report["designs"].items():
        lines.append(f"| {name} | {d['passed']} ({d['pass_rate']:.0%}) | {d['mean_latency_ms']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
