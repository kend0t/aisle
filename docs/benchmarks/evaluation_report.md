# AIsle benchmark report

Generated 2026-10-18 15:39 UTC by `scripts/generate_benchmark_report.py` from the `seed` data source and `gemini-3.8-flash`. Every number below comes from stored events or an evaluation result file.

## Reading accuracy

Source: `eval/results/reader.json`.

Model gemini-3.8-flash, 17 clips, 3 repeats per reader. Labels: an independent frame-by-frame review by Claude (not human labels). Agreement counts only clips whose outcome the review could tell (8 of 17 could not be told from the clip).

| Metric | baseline | single | verified |
|---|---|---|---|
| Outcome agreement with labels | 0.889 | 0.889 | 0.889 |
| Behavior tag F1 | 0.0 | 0.754 | 0.635 |
| Same outcome on every repeat | 16 of 17 | 15 of 17 | 16 of 17 |
| Wrong reads that were flagged | 0 of 3 | 0 of 3 | 0 of 3 |
| Flagged reads that were wrong | None | None | None |
| Unclear clips that were flagged | 0 of 24 | 0 of 24 | 4 of 24 |
| Outcome contradicts own observations | 0 of 51 | 0 of 51 | 0 of 51 |
| Gemini calls per clip | 1.0 | 1.0 | 3.0 |
| Mean latency (ms) | 9009 | 14169 | 15337 |
| Cost per clip (USD, gemini-2.5-flash list prices (gemini-3.8-flash not listed)) | 0.00061 | 0.00099 | 0.003 |

## Copilot numbers

Source: `eval/results/copilot.json`.

Model gemini-3.8-flash, 10 questions, 2 repeats per design.

| Design | Answers with every number right | Mean latency (ms) |
|---|---|---|
| context | 20 of 20 (100%) | 10305 |
| tools | 20 of 20 (100%) | 12800 |

## Stored clips

17 clips. Outcomes are Gemini's readings, checked against labels under 'Reading accuracy'.

| Outcome | Clips | Share of picked up |
|---|---|---|
| Taken | 12 | 75.0% |
| Put back | 4 | 25.0% |
| No pick-up | 1 | - |

Clips per zone: left_bay_cereal 11, right_bay_snacks 6.

These clips were read once each, before verified reading existed.

## Latency

Measured per clip and stored with it (17 clips with Gemini time, 17 with total time).

| Metric | Mean | P95 | Target | Status |
|---|---|---|---|---|
| Gemini reading | 10,980 ms | 17,774 ms | under 3,500 ms | Not met |
| Upload to stored record | 10,416 ms | 14,206 ms | under 5,000 ms | Not met |

Edge frame rate and bandwidth savings are not reported: the camera node does not store them yet.
