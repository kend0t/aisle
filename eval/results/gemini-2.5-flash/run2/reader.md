Model gemini-2.5-flash, 17 clips, 3 repeats per reader. Labels: an independent frame-by-frame review by Claude (not human labels). Agreement counts only clips whose outcome the review could tell (8 of 17 could not be told from the clip).

| Metric | baseline | single | verified |
|---|---|---|---|
| Outcome agreement with labels | 0.704 | 0.704 | 0.667 |
| Behavior tag F1 | 0.0 | 0.625 | 0.674 |
| Same outcome on every repeat | 13 of 17 | 14 of 17 | 14 of 17 |
| Wrong reads that were flagged | 0 of 8 | 0 of 8 | 5 of 9 |
| Flagged reads that were wrong | None | None | 0.714 |
| Unclear clips that were flagged | 0 of 24 | 0 of 24 | 5 of 24 |
| Outcome contradicts own observations | 0 of 51 | 0 of 51 | 0 of 51 |
| Gemini calls per clip | 1.0 | 1.0 | 3.0 |
| Mean latency (ms) | 19270 | 13275 | 22610 |
| Cost per clip (USD, gemini-2.5-flash) | 0.00125 | 0.00171 | 0.00478 |
